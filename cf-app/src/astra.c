#include <assert.h>
#include <inttypes.h>
#include <stdbool.h>

#include "FreeRTOS.h" // IWYU pragma: keep

#include "app.h"
#include "task.h"
#include "uart2.h"

#define DEBUG_MODULE "ASTRA"
#include "debug.h"

#include "crtp_uart2_bridge.h"

#define ASTRA_UART2_BAUDRATE    115200 // Baudrate for UART2 communication with ESP32
#define ASTRA_UART2_DEBOUNCE_MS 10   // Consider a packet complete if no new data is received on UART2 for this many ms
#define ASTRA_CRTP_PORT         0x0E // CRTP port used for communication with ESP32
#define ASTRA_BRIDGE_STACK_SIZE 1024 // Stack size (in words, ie x4 bytes on 32-bit targets)

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

  CrtpUartBridgeConfig_t bridgeConfig = {
      .crtpPort = ASTRA_CRTP_PORT,
      .uartDebounceMs = ASTRA_UART2_DEBOUNCE_MS,
      .taskStackSize = ASTRA_BRIDGE_STACK_SIZE,
      .taskPriority = tskIDLE_PRIORITY + 1,
  };

  DEBUG_PRINT("Starting CRTP <-> UART2 bridge with config: crtpPort=0x%02" PRIx8 ", uartDebounceMs=%" PRIu8 "\n",
              bridgeConfig.crtpPort, bridgeConfig.uartDebounceMs);
  crtpUartBridgeInit(&bridgeConfig);

  DEBUG_PRINT("Initialization complete. Goodbye!\n");
  vTaskDelete(NULL); // Delete the main task since we don't need it anymore
}
