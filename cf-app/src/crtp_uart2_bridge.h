#ifndef ASTRA_CRTP_UART2_BRIDGE_H
#define ASTRA_CRTP_UART2_BRIDGE_H

#include <stdint.h>

#include "FreeRTOS.h" // IWYU pragma: keep

typedef struct {
  // CRTP port used for communication with ESP32
  uint8_t crtpPort;
  // If more than this many ms pass without receiving data on UART, consider the
  // packet complete and send it over CRTP
  uint8_t uartDebounceMs;
  // Stack size for the CRTP <-> UART2 bridge tasks
  uint16_t taskStackSize;
  // Priority for the bridge tasks (default to tskIDLE_PRIORITY + 1 if not set)
  UBaseType_t taskPriority;
} CrtpUartBridgeConfig_t;

/**
 * Initialize the CRTP <-> UART2 bridge.
 */
void crtpUartBridgeInit(const CrtpUartBridgeConfig_t *config);

#endif // ASTRA_CRTP_UART2_BRIDGE_H
