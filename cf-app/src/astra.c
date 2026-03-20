#include <assert.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>

#include "FreeRTOS.h" // IWYU pragma: keep

#include "app.h"
#include "astra_uart.h"
#include "log.h"
#include "param.h"
#include "task.h"
#include "uart2.h"

#define DEBUG_MODULE "ASTRA"
#include "debug.h"

#define ASTRA_UART2_BAUDRATE    115200 // Baudrate for UART2 communication with ESP32
#define ASTRA_UART2_DEBOUNCE_MS 10   // Consider a packet complete if no new data is received on UART2 for this many ms
#define ASTRA_CRTP_PORT         0x0E // CRTP port used for communication with ESP32
#define ASTRA_BRIDGE_STACK_SIZE 1024 // Stack size (in words, ie x4 bytes on 32-bit targets)

// BLE address of the currently bound device (all zeros if unbound)
// We use an uint64 instead of an array of 6 bytes because of the parameters framework
// limiting us to only support params of size 1, 2, 4 or 8.
static uint64_t s_bound_device;

// RSSI value of the currently bound device.
// Put as -1 when no valid RSSI value has been received yet (e.g. right after binding).
static int32_t s_bound_device_rssi = -1;

void astra_uart_bind_request_callback(void) {
  // This callback runs in the context of the param task, so we should not do
  // any heavy work here. Instead, we can just print a debug message for now.
  DEBUG_PRINT("Bind request received for device address 0x%012" PRIx64 "\n", s_bound_device);
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
  DEBUG_PRINT("UART2 initialized with baudrate %" PRId32 "\n", (uint32_t)ASTRA_UART2_BAUDRATE);

  // Initialize the ASTRA UART protocol layer (creates queues and tasks)
  DEBUG_PRINT("Initializing ASTRA UART protocol layer ...\n");
  if (!astra_uart_init()) {
    DEBUG_PRINT("ERROR: Failed to initialize ASTRA UART protocol layer\n");
    return;
  }

  DEBUG_PRINT("Initialization complete. Goodbye!\n");
  vTaskDelete(NULL); // Delete the main task since we don't need it anymore
}

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wpedantic"

// ------------------------------------------------------------------------
// Parameters
// ------------------------------------------------------------------------
PARAM_GROUP_START(astra)
PARAM_ADD_WITH_CALLBACK(PARAM_UINT32, bound_device_low, (uint32_t *)(&s_bound_device), astra_uart_bind_request_callback)
PARAM_ADD_WITH_CALLBACK(PARAM_UINT16, bound_device_hig, (uint16_t *)(&s_bound_device) + 2,
                        astra_uart_bind_request_callback)
PARAM_GROUP_STOP(astra)

// ------------------------------------------------------------------------
// Logging
// ------------------------------------------------------------------------
LOG_GROUP_START(astra)
LOG_ADD(LOG_UINT32, bound_device_low, (uint32_t *)(&s_bound_device))
LOG_ADD(LOG_UINT16, bound_device_hig, (uint16_t *)(&s_bound_device) + 2)
LOG_ADD(LOG_UINT32, bound_device_rssi, (uint32_t *)&s_bound_device_rssi)
LOG_GROUP_STOP(astra)

#pragma GCC diagnostic pop
