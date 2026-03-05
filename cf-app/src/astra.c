#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "FreeRTOSConfig.h"
#include "app.h"

#include "FreeRTOS.h" // IWYU pragma: keep
#include "queue.h"
#include "task.h"

#include "crtp.h"
#include "uart2.h"

#define DEBUG_MODULE "ASTRA"
#include "debug.h"

#define ASTRA_UART2_BAUDRATE 115200

// CRTP port for ESP32 communication
#define CRTP_PORT_ESP32 0x0E

// Delay in ticks for the UART polling task
#define ASTRA_ESP32_UART_POLLING_INTERVAL M2T(10) // 10 ms

static xQueueHandle esp32Queue;

// Forward data from CRTP to UART2
void crtpPortEsp32Handler(CRTPPacket *packet) {
  DEBUG_PRINT("(RADIO) Received packet on port %d with size %d\n", CRTP_PORT_ESP32, packet->size);

  xQueueSend(esp32Queue, packet, 0);
}

void crtpToEsp32Task(void *params) {
  (void)params;

  static CRTPPacket packet;

  while (true) {
    if (xQueueReceive(esp32Queue, &packet, portMAX_DELAY) == pdPASS) {
      // Send the received CRTP packet data to UART2
      DEBUG_PRINT("(CRTP -> UART2) Forwarding packet with size %d\n", packet.size);
      uart2SendData(packet.size, packet.data);
    }
  }
}

// Task to read data from UART2 and send it as CRTP packets
// This task is NOT thread safe.
void esp32ToCrtpTask(void *params) {
  (void)params;

  static CRTPPacket packet;

  while (true) {
    uint32_t bytesRead = uart2GetDataWithTimeout(sizeof(packet.data), packet.data, ASTRA_ESP32_UART_POLLING_INTERVAL);

    if (bytesRead > 0) {

      DEBUG_PRINT("(UART2 -> CRTP) Read %lu bytes from UART2, forwarding as CRTP packet\n", bytesRead);

      // Read data from UART2 and send it as a CRTP packet
      packet.size = bytesRead;
      packet.header = CRTP_HEADER(CRTP_PORT_ESP32, 0); // Channel 0

      // We use block because otherwise we'd have to malloc the packet,
      // otherwise we'd have a dangling pointer in the queue as soon as
      // we return from this function.
      crtpSendPacketBlock(&packet);

      // Yield to allow other tasks to run
      taskYIELD(); // NOLINT(clang-analyzer-core.FixedAddressDereference)
    } else {
      vTaskDelay(ASTRA_ESP32_UART_POLLING_INTERVAL);
    }
  }
}

void appMain() {
  DEBUG_PRINT("Waiting for activation ...\n");

  { // Initialize UART2
    DEBUG_PRINT("Initializing UART2 ...\n");
    uart2Init(ASTRA_UART2_BAUDRATE);
    if (!uart2Test()) {
      DEBUG_PRINT("ERROR: Failed to initialize UART2\n");
      return;
    }
    DEBUG_PRINT("UART1 initialized with baudrate %d\n", ASTRA_UART2_BAUDRATE);
  }

  { // Create queue for CRTP <-> UART2 communication
    esp32Queue = xQueueCreate(10, sizeof(CRTPPacket));
    if (esp32Queue == NULL) {
      DEBUG_PRINT("ERROR: Failed to create queue for ESP32 communication\n");
      return;
    }
  }

  { // Register CRTP handler
    DEBUG_PRINT("Registering CRTP handler for ESP32 ...\n");
    crtpRegisterPortCB(CRTP_PORT_ESP32, crtpPortEsp32Handler);
    DEBUG_PRINT("CRTP handler for ESP32 registered on port %d\n", CRTP_PORT_ESP32);
  }

  { // Create task to forward data from UART2 to CRTP
    DEBUG_PRINT("Creating task to forward data from UART1 to CRTP ...\n");
    xTaskCreate(esp32ToCrtpTask, "ASTRA-E2C", 512, NULL, tskIDLE_PRIORITY + 1, NULL);
    DEBUG_PRINT("Task to forward data from UART1 to CRTP created\n");
  }

  { // Create task to forward data from CRTP to UART2
    DEBUG_PRINT("Creating task to forward data from CRTP to UART1 ...\n");
    xTaskCreate(crtpToEsp32Task, "ASTRA-C2E", 512, NULL, tskIDLE_PRIORITY + 1, NULL);
    DEBUG_PRINT("Task to forward data from CRTP to UART1 created\n");
  }

  DEBUG_PRINT("Initialization complete. Goodbye!\n");
  vTaskDelete(NULL); // Delete the main task since we don't need it anymore
}
