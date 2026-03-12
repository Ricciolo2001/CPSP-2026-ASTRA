#pragma once

#include <stdint.h>

typedef struct {
  // CRTP port used for communication with ESP32
  uint8_t crtpPort;
  // If more than this many ms pass without receiving data on UART, consider the packet complete
  // and send it over CRTP
  uint8_t uartDebounceMs;
} CrtpUartBridgeConfig_t;

/**
 * Initialize the CRTP <-> UART2 bridge.
 */
void crtpUartBridgeInit(CrtpUartBridgeConfig_t *config);
