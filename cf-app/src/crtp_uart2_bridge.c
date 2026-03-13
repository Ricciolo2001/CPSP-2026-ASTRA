#include "crtp_uart2_bridge.h"

#include <inttypes.h>

// Suppress warnings about missing prototypes in firmware headers
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wstrict-prototypes"

#include "FreeRTOS.h" // IWYU pragma: keep
#include "FreeRTOSConfig.h"
#include "crtp.h"
#include "projdefs.h"
#include "queue.h"
#include "task.h"
#include "uart2.h"

#define DEBUG_MODULE "CRTP_UART2_BRIDGE"
#include "debug.h"

#pragma GCC diagnostic pop

static TaskHandle_t uartToCrtpTaskHandle = NULL;
static TaskHandle_t crtpToUartTaskHandle = NULL;

/**
 * Task: UART2 -> CRTP
 */
static void uartToCrtpTask(void *params) {
  const CrtpUartBridgeConfig_t *ctx = (const CrtpUartBridgeConfig_t *)params;
  const uint32_t debounceTicks = M2T(10); // 10 ms debounce

  CRTPPacket packet = {.header = (uint8_t)CRTP_HEADER(ctx->crtpPort, 0)};

  while (true) {
    // Read data from UART2
    int32_t bytesRead = uart2GetDataWithTimeout(sizeof(packet.data), packet.data, debounceTicks);

    // If we read any data, send it as a CRTP packet
    if (bytesRead > 0) {
      ASSERT((uint32_t)bytesRead <= sizeof(packet.data)); // Ensure we don't overflow the packet data buffer

      DEBUG_PRINT("UART2 -> CRTP: size=%d\n", (int)bytesRead);
      packet.size = (uint8_t)bytesRead;
      if (crtpSendPacket(&packet) != pdPASS) {
        DEBUG_PRINT("WARN: CRTP send failed for packet of size %u\n", (unsigned int)packet.size);
      }
    }
  }
}

/**
 * Task: CRTP -> UART2
 */
static void crtpToUartTask(void *params) {
  const CrtpUartBridgeConfig_t *ctx = (const CrtpUartBridgeConfig_t *)params;
  CRTPPacket packet;

  while (true) {
    // Wait for a CRTP packet to be received on the specified port
    if (crtpReceivePacketBlock(ctx->crtpPort, &packet) == pdPASS) {
      // If we received a packet, send its data over UART2
      DEBUG_PRINT("CRTP -> UART2: size=%u\n", (unsigned int)packet.size);
      uart2SendData(packet.size, packet.data);
    }
  }
}

void crtpUartBridgeInit(CrtpUartBridgeConfig_t *const config) {
  DEBUG_PRINT("Creating CRTP queue ... \n");
  crtpInitTaskQueue(config->crtpPort);

  // Create task to forward data UART2 -> CRTP
  DEBUG_PRINT("Creating task to forward data from UART2 to CRTP ...\n");
  xTaskCreate(uartToCrtpTask, "ASTRA-U2C", configMINIMAL_STACK_SIZE, config, tskIDLE_PRIORITY + 1,
              &uartToCrtpTaskHandle);
  DEBUG_PRINT("Task to forward data from UART2 to CRTP created\n");

  // Create task to forward data CRTP -> UART2
  DEBUG_PRINT("Creating task to forward data from CRTP to UART2 ...\n");
  xTaskCreate(crtpToUartTask, "ASTRA-C2U", configMINIMAL_STACK_SIZE, config, tskIDLE_PRIORITY + 1,
              &crtpToUartTaskHandle);
  DEBUG_PRINT("Task to forward data from CRTP to UART2 created\n");
}

void crtpUartBridgeDeinit(void) {
  // Delete the UART2 -> CRTP task
  if (uartToCrtpTaskHandle != NULL) {
    vTaskDelete(uartToCrtpTaskHandle);
    uartToCrtpTaskHandle = NULL;
    DEBUG_PRINT("UART2 -> CRTP task deleted\n");
  }

  // Delete the CRTP -> UART2 task
  if (crtpToUartTaskHandle != NULL) {
    vTaskDelete(crtpToUartTaskHandle);
    crtpToUartTaskHandle = NULL;
    DEBUG_PRINT("CRTP -> UART2 task deleted\n");
  }
}
