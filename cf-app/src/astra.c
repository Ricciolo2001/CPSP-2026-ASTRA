#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "app.h"

#include "FreeRTOS.h" // IWYU pragma: keep
#include "task.h"

#include "uart1.h"
#include "crtp.h"

#define DEBUG_MODULE "ASTRA"
#include "debug.h"

#define ASTRA_UART1_BAUDRATE 115200

// CRTP port for ESP32 communication
#define CRTP_PORT_ESP32 0x0E

// Delay in ticks for the UART polling task
#define ASTRA_ESP32_UART_POLLING_INTERVAL M2T(10) // 10 ms

// Forward data from CRTP to UART1
void crtpPortEsp32Handler(CRTPPacket *packet)
{
  uart1SendData(packet->size, packet->data);
  DEBUG_PRINT("Forwarded data (CRTP -> UART1): %.*s\n", packet->size, packet->data);
}

// Task to read data from UART1 and send it as CRTP packets
// This task is NOT thread safe.
void esp32ToCrtpTask(void *params)
{
  (void)params;

  static CRTPPacket packet;

  while (true)
  {
    uint32_t bytesRead = uart1bytesAvailable();
    if (bytesRead > 0)
    {
      // Cap the number of bytes read to the maximum data size of a CRTP packet
      uint32_t toRead = bytesRead < sizeof(packet.data) ? bytesRead : sizeof(packet.data);

      // Read data from UART1 and send it as a CRTP packet
      uart1GetBytesWithDefaultTimeout(toRead, packet.data);
      packet.size = toRead;
      packet.header = CRTP_HEADER(CRTP_PORT_ESP32, 0); // Channel 0

      // We use block because otherwise we'd have to malloc the packet,
      // otherwise we'd have a dangling pointer in the queue as soon as
      // we return from this function.
      crtpSendPacketBlock(&packet);

      DEBUG_PRINT("Forwarded data (UART1 -> CRTP): %.*s\n", packet.size, packet.data);

      // Yield to allow other tasks to run
      taskYIELD(); // NOLINT(clang-analyzer-core.FixedAddressDereference)
    }
    else
    {
      vTaskDelay(ASTRA_ESP32_UART_POLLING_INTERVAL);
    }
  }
}

void appMain()
{
  DEBUG_PRINT("Waiting for activation ...\n");

  DEBUG_PRINT("Initializing UART1 ...\n");
  uart1Init(ASTRA_UART1_BAUDRATE);
  if (!uart1Test())
  {
    DEBUG_PRINT("ERROR: Failed to initialize UART1\n");
    return;
  }
  DEBUG_PRINT("UART1 initialized with baudrate %d\n", ASTRA_UART1_BAUDRATE);

  DEBUG_PRINT("Registering CRTP handler for ESP32 ...\n");
  crtpRegisterPortCB(CRTP_PORT_ESP32, crtpPortEsp32Handler);
  DEBUG_PRINT("CRTP handler for ESP32 registered on port %d\n", CRTP_PORT_ESP32);

  DEBUG_PRINT("Creating task to forward data from UART1 to CRTP ...\n");
  xTaskCreate(esp32ToCrtpTask, "ASTRA-E2C", 512, NULL, tskIDLE_PRIORITY + 1, NULL);
  DEBUG_PRINT("Task to forward data from UART1 to CRTP created\n");

  DEBUG_PRINT("Initialization complete. Goodbye!\n");
  vTaskDelete(NULL); // Delete the main task since we don't need it anymore
}
