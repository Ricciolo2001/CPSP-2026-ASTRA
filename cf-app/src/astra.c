#include <assert.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

// Suppress warnings about missing prototypes in firmware headers
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wstrict-prototypes"

#include "FreeRTOSConfig.h"
#include "app.h"

#include "FreeRTOS.h" // IWYU pragma: keep
#include "crtp.h"
#include "projdefs.h"
#include "queue.h"
#include "task.h"
#include "uart2.h"

#define DEBUG_MODULE "ASTRA"
#include "debug.h"

#pragma GCC diagnostic pop

#define ASTRA_UART2_BAUDRATE         115200  // Baudrate for UART2 communication with ESP32
#define ASTRA_UART2_POLLING_INTERVAL M2T(10) // 10 ms
#define ASTRA_CRTP_PORT              0x0E    // CRTP port used for communication with ESP32
#define ASTRA_QUEUE_LEN              10      // Length of the queue for CRTP <-> UART2 communication
#define ASTRA_TASK_STACK_SIZE        128     // Stack size for the FreeRTOS tasks (in words, not bytes)

typedef struct {
  uint8_t crtpPort;
} AstraContext_t;

// Persistent context for the lifetime of the tasks
static AstraContext_t astraContext;

/**
 * Task: UART2 -> CRTP
 */
static void uartToCrtpTask(void *params) {
  const AstraContext_t *ctx = (const AstraContext_t *)params;
  const uint32_t debounceTicks = M2T(10); // 10 ms debounce

  CRTPPacket packet = {.header = (uint8_t)CRTP_HEADER(ctx->crtpPort, 0)};

  while (true) {
    // Read data from UART2
    int32_t bytesRead = uart2GetDataWithTimeout(sizeof(packet.data), packet.data, debounceTicks);

    // If we read any data, send it as a CRTP packet
    if (bytesRead > 0) {
      ASSERT((uint32_t)bytesRead <= sizeof(packet.data)); // Ensure we don't overflow the packet data buffer

      DEBUG_PRINT("UART2 -> CRTP: size=%" PRIu32 "\n", bytesRead);
      packet.size = (uint8_t)bytesRead;
      crtpSendPacketBlock(&packet);
    }
  }
}

/**
 * Task: CRTP -> UART2
 */
static void crtpToUartTask(void *params) {
  const AstraContext_t *ctx = (const AstraContext_t *)params;
  CRTPPacket packet;

  while (true) {
    // Wait for a CRTP packet to be received on the specified port
    if (crtpReceivePacketBlock(ctx->crtpPort, &packet) == pdPASS) {
      // If we received a packet, send its data over UART2
      DEBUG_PRINT("CRTP -> UART2: size=%" PRIu8 "\n", packet.size);
      uart2SendData(packet.size, packet.data);
    }
  }
}

void appInit(void) {
  astraContext = (AstraContext_t){
      .crtpPort = ASTRA_CRTP_PORT,
  };

  // Initialize UART2
  const uint32_t uart2Baudrate = ASTRA_UART2_BAUDRATE;
  DEBUG_PRINT("Initializing UART2 ...\n");
  uart2Init(uart2Baudrate);
  if (!uart2Test()) {
    DEBUG_PRINT("ERROR: Failed to initialize UART2\n");
    return;
  }
  DEBUG_PRINT("UART2 initialized with baudrate %" PRId32 "\n", uart2Baudrate);
}

void appMain(void) {

  // Create task to forward data UART2 -> CRTP
  DEBUG_PRINT("Creating task to forward data from UART1 to CRTP ...\n");
  xTaskCreate(uartToCrtpTask, "ASTRA-E2C", ASTRA_TASK_STACK_SIZE, &astraContext, tskIDLE_PRIORITY + 1, NULL);
  DEBUG_PRINT("Task to forward data from UART1 to CRTP created\n");

  // Create task to forward data CRTP -> UART2
  DEBUG_PRINT("Creating task to forward data from CRTP to UART1 ...\n");
  xTaskCreate(crtpToUartTask, "ASTRA-C2E", ASTRA_TASK_STACK_SIZE, &astraContext, tskIDLE_PRIORITY + 1, NULL);
  DEBUG_PRINT("Task to forward data from CRTP to UART1 created\n");

  DEBUG_PRINT("Initialization complete. Goodbye!\n");
  vTaskDelete(NULL); // Delete the main task since we don't need it anymore
}
