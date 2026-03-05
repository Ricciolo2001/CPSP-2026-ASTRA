#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "FreeRTOSConfig.h"
#include "app.h"

#include "FreeRTOS.h" // IWYU pragma: keep
#include "crtp.h"
#include "queue.h"
#include "task.h"
#include "uart2.h"

#define DEBUG_MODULE "ASTRA"
#include "debug.h"

// Baudrate for UART2 communication with ESP32
#define ASTRA_UART2_BAUDRATE 115200

// CRTP port for ESP32 communication
#define ASTRA_CRTP_PORT 0x0E

// Delay in ticks for the UART polling task
#define ASTRA_ESP32_UART_POLLING_INTERVAL M2T(10) // 10 ms

static xQueueHandle esp32Queue;

struct crtp_uart_bridge {
  uint32_t uart_port; // UART port number (e.g., 2 for UART2)
  xQueueHandle queue; // Queue for CRTP packets
};

// This function is called by the CRTP handler when a packet is received on the ESP32 port.
void crtpPortEsp32Handler(CRTPPacket *packet) { xQueueSend(esp32Queue, packet, 0); }

// Task to read CRTP packets from the queue and send them to UART2
// This task is NOT thread safe.
void crtpToEsp32Task(void *params) {
  (void)params;

  static CRTPPacket packet;

  while (true) {
    if (xQueueReceive(esp32Queue, &packet, portMAX_DELAY) == pdPASS) {
      DEBUG_PRINT("CRTP -> UART2: size=%" PRIu8 "\n", packet.size);
      uart2SendData(packet.size, packet.data);
    }
  }
}

// Task to read data from UART2 and send it as CRTP packets
// This task is NOT thread safe.
void esp32ToCrtpTask(void *params) {

  static CRTPPacket packet;

  const uint32_t maxDataSize = sizeof(packet.data);
  const uint32_t port = ASTRA_CRTP_PORT;
  const uint32_t channel = 0;
  const uint32_t timeoutTicks = ASTRA_ESP32_UART_POLLING_INTERVAL;

  while (true) {
    uint32_t bytesRead = uart2GetDataWithTimeout(maxDataSize, packet.data, timeoutTicks);

    if (bytesRead > 0) {
      DEBUG_PRINT("UART2 -> CRTP: size=%" PRIu32 "\n", bytesRead);

      // Read data from UART2 and send it as a CRTP packet
      packet.size = bytesRead;
      packet.header = CRTP_HEADER(port, channel);

      // We use block because otherwise we'd have to malloc the packet,
      // otherwise we'd have a dangling pointer in the queue as soon as
      // we return from this function.
      crtpSendPacketBlock(&packet);
    }

    // Yield to allow other tasks to run
    taskYIELD(); // NOLINT(clang-analyzer-core.FixedAddressDereference)
  }
}

void appMain() {
  DEBUG_PRINT("Waiting for activation ...\n");

  { // Initialize UART2
    DEBUG_PRINT("Initializing UART2 ...\n");
    const uint32_t baudrate = ASTRA_UART2_BAUDRATE;
    uart2Init(baudrate);
    if (!uart2Test()) {
      DEBUG_PRINT("ERROR: Failed to initialize UART2\n");
      return;
    }
    DEBUG_PRINT("UART2 initialized with baudrate %" PRId32 "\n", baudrate);
  }

  { // Create queue for CRTP <-> UART2 communication
    esp32Queue = xQueueCreate(10, sizeof(CRTPPacket));
    if (esp32Queue == NULL) {
      DEBUG_PRINT("ERROR: Failed to create queue for ESP32 communication\n");
      return;
    }
  }

  { // Register CRTP handler
    const int32_t crtpPort = ASTRA_CRTP_PORT;
    DEBUG_PRINT("Registering CRTP handler for ESP32 ...\n");
    crtpRegisterPortCB(crtpPort, crtpPortEsp32Handler);
    DEBUG_PRINT("CRTP handler for ESP32 registered on port %" PRId32 "\n", crtpPort);
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
