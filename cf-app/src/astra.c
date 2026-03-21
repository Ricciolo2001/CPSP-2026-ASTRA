#include <assert.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "FreeRTOS.h" // IWYU pragma: keep

#include "app.h"
#include "log.h"
#include "param.h"
#include "task.h"
#include "uart2.h"

#include "protocol/astra_uart.h"

#define DEBUG_MODULE "ASTRA"
#include "debug.h"

#define ASTRA_UART2_BAUDRATE    115200 // Baudrate for UART2 communication with ESP32
#define ASTRA_BRIDGE_STACK_SIZE 1024   // Stack size (in words, ie x4 bytes on 32-bit targets)

// BLE address of the currently bound device (all zeros if unbound)
// We use an uint64 instead of an array of 6 bytes because of the parameters framework
// limiting us to only support params of size 1, 2, 4 or 8.
static uint64_t s_bound_device;

// RSSI value of the currently bound device.
// Put as -1 when no valid RSSI value has been received yet (e.g. right after binding).
static int32_t s_bound_device_rssi = -1;

void astra_uart_bind_request_callback(void) {

  // Copy the bound device address
  astra_dev_addr_t device_addr;
  memcpy(device_addr.bytes, &s_bound_device, ASTRA_BLE_ADDR_LEN);

  const astra_dev_addr_t zero_addr = {{0}};
  bool wants_unbind = (astra_dev_addr_cmp(&device_addr, &zero_addr) == 0);

  if (wants_unbind) {
    astra_uart_packet_t unbind_request = {
        .type = ASTRA_UART_UNBIND_REQUEST,
    };
    astra_uart_send(&unbind_request, portMAX_DELAY);
    DEBUG_PRINT("Sent unbind request for device %02x:%02x:%02x:%02x:%02x:%02x\n", device_addr.bytes[0],
                device_addr.bytes[1], device_addr.bytes[2], device_addr.bytes[3], device_addr.bytes[4],
                device_addr.bytes[5]);
  } else {
    // Create a bind request and add it to the ASTRA UART protocol layer's outgoing queue
    astra_uart_bind_request_t bind_request = {.device_addr = device_addr};
    astra_uart_packet_t packet = {
        .type = ASTRA_UART_BIND_REQUEST,
        .payload.bind_request = bind_request,
    };

    astra_uart_send(&packet, portMAX_DELAY);
    DEBUG_PRINT("Sent bind request for device %02x:%02x:%02x:%02x:%02x:%02x\n", device_addr.bytes[0],
                device_addr.bytes[1], device_addr.bytes[2], device_addr.bytes[3], device_addr.bytes[4],
                device_addr.bytes[5]);
  }
}

void astra_uart_bridge_task(void *params) {
  (void)params;
  astra_uart_packet_t packet;

  while (true) {
    if (!astra_uart_receive(&packet, portMAX_DELAY)) {
      DEBUG_PRINT("Failed to receive packet from ASTRA UART protocol layer\n");
      continue; // This should never happen since we're blocking indefinitely, but handle it just in case
    }

    switch (packet.type) {
    case ASTRA_UART_BIND_RESPONSE:
      if (!packet.payload.bind_response.success) {
        DEBUG_PRINT("Bind failed.\n");
        s_bound_device = 0;
        break;
      }

      DEBUG_PRINT("Bind successful!\n");
      break;

    case ASTRA_UART_UNBIND_RESPONSE:
      DEBUG_PRINT("Unbind successful!\n");

      s_bound_device = 0;
      s_bound_device_rssi = -1;
      break;

    case ASTRA_UART_RSSI_VALUE:
      s_bound_device_rssi = packet.payload.rssi_value.rssi;
      DEBUG_PRINT("Received RSSI value: %d dBm\n", (int)s_bound_device_rssi);
      break;

    default:
      DEBUG_PRINT("Received unexpected packet type: 0x%02x\n", (unsigned)packet.type);
      break;
    }
  }
}

void appMain(void) {
  DEBUG_PRINT("Initializing ASTRA application...\n");

  // Initialize UART2
  DEBUG_PRINT("Initializing UART2 ...\n");
  uart2Init(ASTRA_UART2_BAUDRATE);
  if (!uart2Test()) {
    DEBUG_PRINT("ERROR: Failed to initialize UART2\n");
    return;
  }
  DEBUG_PRINT("UART2 initialized with baudrate %" PRIu32 "\n", (uint32_t)ASTRA_UART2_BAUDRATE);

  // Initialize the ASTRA UART protocol layer (creates queues and tasks)
  DEBUG_PRINT("Initializing ASTRA UART protocol layer ...\n");
  if (!astra_uart_init()) {
    DEBUG_PRINT("ERROR: Failed to initialize ASTRA UART protocol layer\n");
    return;
  }

  // Take new packets from the ASTRA UART protocol layer
  if (xTaskCreate(astra_uart_bridge_task, "astra_uart_bridge", ASTRA_BRIDGE_STACK_SIZE, NULL, CONFIG_APP_PRIORITY,
                  NULL) != pdPASS) {
    DEBUG_PRINT("ERROR: Failed to create ASTRA UART bridge task\n");
    return;
  }

  DEBUG_PRINT("Initialization complete. Goodbye!\n");
  vTaskDelete(NULL); // Delete the main task since we don't need it anymore
}

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wpedantic"

// Static assertions to ensure our assumptions about struct sizes and BLE address length hold true.
static_assert(sizeof(s_bound_device) == 8, "s_bound_device must be 8 bytes");
static_assert(ASTRA_BLE_ADDR_LEN == 6, "BLE address must be 6 bytes");

// ------------------------------------------------------------------------
// Parameters
// ------------------------------------------------------------------------
PARAM_GROUP_START(astra)
PARAM_ADD(PARAM_UINT32, bound_device_low, (uint32_t *)(&s_bound_device))
PARAM_ADD_WITH_CALLBACK(PARAM_UINT16, bound_device_hig, (uint16_t *)(&s_bound_device) + 2,
                        astra_uart_bind_request_callback)
PARAM_GROUP_STOP(astra)

// ------------------------------------------------------------------------
// Logging
// ------------------------------------------------------------------------
LOG_GROUP_START(astra)
LOG_ADD(LOG_UINT32, bound_device_low, (uint32_t *)(&s_bound_device))
LOG_ADD(LOG_UINT16, bound_device_hig, (uint16_t *)(&s_bound_device) + 2)
LOG_ADD(LOG_INT32, bound_device_rssi, (uint32_t *)&s_bound_device_rssi)
LOG_GROUP_STOP(astra)

#pragma GCC diagnostic pop
