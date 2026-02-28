#include "deck.h"
#include "uart.h"
#include "FreeRTOS.h" // Because yes
#include "task.h"
#include "debug.h"
#include <string.h>

#define UART_PORT       UART2 // !Non ho capito quale conviene usare, ci stanno la 1 e la 2, chattino l'ha messa 2
#define UART_BAUDRATE   115200  // Standard for esp32-c3
 
#define HANDSHAKE_MSG   "HELLO\n"
#define HANDSHAKE_REPLY "OK\n"

static bool isInit = false;
static bool isDetected = false;

// ===== UART TASK =============

static void uartTask(void *param)
{
    uint8_t c;
    char buffer[32];
    int idx = 0;

    while (1)
    {
        if (uartGetChar(UART_PORT, &c))
        {
            if (c == '\n')
            {
                buffer[idx] = 0;

                if (strcmp(buffer, "OK") == 0)
                {
                    DEBUG_PRINT("ESP32 Handshake OK\n");
                }

                idx = 0;
            }
            else
            {
                if (idx < sizeof(buffer)-1)
                {
                    buffer[idx++] = c;
                }
            }
        }

        vTaskDelay(M2T(5));
    }
}

// ===== INIT FUNCTION =========

static void deckInit(DeckInfo *info)
{
    if (isInit)
        return;

    DEBUG_PRINT("UART ESP32 Deck Initialization\n");

    uartInit(UART_PORT, UART_BAUDRATE);

    delay(1000); // !Rimuovi, qui solo per sanità mentale ed evitare bug stupidi

    /* Send handshake */
    uartPutString(UART_PORT, HANDSHAKE_MSG);

    xTaskCreate(uartTask,
                "ESP32_UART",
                256,
                NULL,
                2,
                NULL);

    isInit = true;
}

// ===== DECK DRIVER STRUCT ====

static const DeckDriver deckDriver = {
    .vid = 0xBC,
    .pid = 0x10,
    .name = "uart_esp32",
    .usedGpio = DECK_USING_UART2,
    .init = deckInit,
    .test = deckTest,
};

DECK_DRIVER(deckDriver);
