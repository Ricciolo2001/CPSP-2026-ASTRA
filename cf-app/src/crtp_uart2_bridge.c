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

      DEBUG_PRINT("UART2 -> CRTP: size=%" PRIu32 "\n", bytesRead);
      packet.size = (uint8_t)bytesRead;
      if (crtpSendPacketBlock(&packet) != pdPASS) {
        DEBUG_PRINT("ERROR: Failed to send CRTP packet\n");
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
      DEBUG_PRINT("CRTP -> UART2: size=%" PRIu8 "\n", packet.size);
      uart2SendData(packet.size, packet.data);
    }
  }
}

void crtpUartBridgeInit(CrtpUartBridgeConfig_t *const config) {
  // Create task to forward data UART2 -> CRTP
  DEBUG_PRINT("Creating task to forward data from UART2 to CRTP ...\n");
  xTaskCreate(uartToCrtpTask, "CRTP_UART2_BRIDGE-U2C", configMINIMAL_STACK_SIZE, config, tskIDLE_PRIORITY + 1, NULL);
  DEBUG_PRINT("Task to forward data from UART2 to CRTP created\n");

  // Create task to forward data CRTP -> UART2
  DEBUG_PRINT("Creating task to forward data from CRTP to UART2 ...\n");
  xTaskCreate(crtpToUartTask, "CRTP_UART2_BRIDGE-C2U", configMINIMAL_STACK_SIZE, config, tskIDLE_PRIORITY + 1, NULL);
  DEBUG_PRINT("Task to forward data from CRTP to UART2 created\n");
}
