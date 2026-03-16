#include "crtp_uart2_bridge.h"

#include <inttypes.h>

#include "FreeRTOS.h" // IWYU pragma: keep
#include "FreeRTOSConfig.h"
#include "crtp.h"
#include "projdefs.h"
#include "queue.h"
#include "task.h"
#include "uart2.h"

#define DEBUG_MODULE "CRTP_UART2_BRIDGE"
#include "debug.h"

static CrtpUartBridgeConfig_t bridgeConfig;
static TaskHandle_t uartToCrtpTaskHandle = NULL;
static TaskHandle_t crtpToUartTaskHandle = NULL;

/**
 * Task: UART2 -> CRTP
 */
static void uartToCrtpTask(void *params) {
  (void)params;
  const uint32_t debounceTicks = M2T(bridgeConfig.uartDebounceMs);

  CRTPPacket packet = {.header = (uint8_t)CRTP_HEADER(bridgeConfig.crtpPort, 0)};

  while (true) {
    // Read data from UART2
    int32_t bytesRead = uart2GetDataWithTimeout(sizeof(packet.data), packet.data, debounceTicks);

    // If we read any data, send it as a CRTP packet
    if (bytesRead > 0) {
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
  (void)params;
  CRTPPacket packet;

  while (true) {
    // Wait for a CRTP packet to be received on the specified port
    if (crtpReceivePacketBlock(bridgeConfig.crtpPort, &packet) != pdPASS) {
      DEBUG_PRINT("WARN: Failed to receive CRTP packet on port 0x%02" PRIx8 "\n", bridgeConfig.crtpPort);
      continue;
    }

    // Send it out over UART2
    DEBUG_PRINT("CRTP -> UART2: size=%u\n", (unsigned int)packet.size);
    uart2SendData(packet.size, packet.data);
  }
}

void crtpUartBridgeInit(const CrtpUartBridgeConfig_t *config) {
  if (crtpToUartTaskHandle != NULL || uartToCrtpTaskHandle != NULL) {
    DEBUG_PRINT("ERROR: CRTP UART bridge tasks are already running\n");
    return;
  }

  bridgeConfig = *config; // Store the config for use in tasks

  DEBUG_PRINT("Creating CRTP queue ... \n");
  crtpInitTaskQueue(bridgeConfig.crtpPort);

  // Create task to forward data UART2 -> CRTP
  DEBUG_PRINT("Creating task to forward data from UART2 to CRTP ...\n");
  if (xTaskCreate(uartToCrtpTask, "ASTRA-U2C", bridgeConfig.taskStackSize, NULL, bridgeConfig.taskPriority,
                  &uartToCrtpTaskHandle) != pdPASS) {
    DEBUG_PRINT("ERROR: Failed to create UART2 -> CRTP task\n");
    return;
  }
  DEBUG_PRINT("Task to forward data from UART2 to CRTP created\n");

  // Create task to forward data CRTP -> UART2
  DEBUG_PRINT("Creating task to forward data from CRTP to UART2 ...\n");
  if (xTaskCreate(crtpToUartTask, "ASTRA-C2U", bridgeConfig.taskStackSize, NULL, bridgeConfig.taskPriority,
                  &crtpToUartTaskHandle) != pdPASS) {
    DEBUG_PRINT("ERROR: Failed to create CRTP -> UART2 task\n");
    // Clean up the previously created task
    vTaskDelete(uartToCrtpTaskHandle);
    uartToCrtpTaskHandle = NULL;
    return;
  }
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
