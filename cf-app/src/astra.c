#include <assert.h>
#include <inttypes.h>
#include <stdbool.h>

// Suppress warnings about missing prototypes in firmware headers
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wstrict-prototypes"

#include "FreeRTOSConfig.h"
#include "app.h"

#include "FreeRTOS.h" // IWYU pragma: keep
#include "task.h"
#include "uart2.h"

#define DEBUG_MODULE "ASTRA"
#include "debug.h"

#pragma GCC diagnostic pop

#include "crtp_uart2_bridge.h"

#define ASTRA_UART2_BAUDRATE         115200  // Baudrate for UART2 communication with ESP32
#define ASTRA_UART2_POLLING_INTERVAL M2T(10) // 10 ms
#define ASTRA_CRTP_PORT              0x0E    // CRTP port used for communication with ESP32

void appMain(void) {
  DEBUG_PRINT("Initializing ASTRA application...\n");

  // Initialize UART2
  const uint32_t uart2Baudrate = ASTRA_UART2_BAUDRATE;
  DEBUG_PRINT("Initializing UART2 ...\n");
  uart2Init(uart2Baudrate);
  if (!uart2Test()) {
    DEBUG_PRINT("ERROR: Failed to initialize UART2\n");
    return;
  }
  DEBUG_PRINT("UART2 initialized with baudrate %" PRId32 "\n", uart2Baudrate);

  CrtpUartBridgeConfig_t bridgeConfig = {
      .crtpPort = ASTRA_CRTP_PORT,
      .uartDebounceMs = ASTRA_UART2_POLLING_INTERVAL / M2T(1), // Convert polling interval from ticks to ms
  };

  DEBUG_PRINT("Starting CRTP <-> UART2 bridge with config: crtpPort=0x%02" PRIx8 ", uartDebounceMs=%" PRIu8 "\n",
              bridgeConfig.crtpPort, bridgeConfig.uartDebounceMs);
  crtpUartBridgeInit(&bridgeConfig);

  DEBUG_PRINT("Initialization complete. Goodbye!\n");
  vTaskDelete(NULL); // Delete the main task since we don't need it anymore
}
