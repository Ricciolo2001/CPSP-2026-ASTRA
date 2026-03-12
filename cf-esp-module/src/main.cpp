#include <stdio.h>
#include <stdlib.h>

#include <Arduino.h>
#include <driver/gpio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <sdkconfig.h>

#include "BleManager.h"
#include "UartDaemon.h"
#include "struct/UartTaskParams.h"

#define UART_PORT_NUM (UART_NUM_1)
#define UART_BAUD_RATE (115200)

// !================================================

/**
 * This is an example which echos any data it receives on configured UART back
 * to the sender, with hardware flow control turned off. It does not use UART
 * driver event queue.
 *
 * - Port: configured UART
 * - Receive (Rx) buffer: on
 * - Transmit (Tx) buffer: off
 * - Flow control: off
 * - Event queue: off
 * - Pin assignment: see defines below (See Kconfig)
 */

// !================================================

static BleManager ble;
static UartDaemon uartDaemon{UART_PORT_NUM, UART_BAUD_RATE, &ble};

// =================================================

void setup() {
    Serial.begin(115200);
    delay(1000); // Better safe than sorry?
    Serial.println("Serial monitor setup complete.");

    // BLE initial setup
    ble.init();
    Serial.println("BLE Manager initialized.");

    pinMode(BUILTIN_LED, OUTPUT);
    digitalWrite(BUILTIN_LED, HIGH); // LOW turns the LED on, HIGH turns it off
                                     // like who designed that?

    // ?This is for the oler version, if the new works please delete
    // Uart reciever task creation
    // UartTaskParams *params = new UartTaskParams;
    // params->port = UART_PORT_NUM;
    // params->baudrate = UART_BAUD_RATE;
    // params->ble = &ble;

    uartDaemon.start();

    vTaskDelete(NULL); // Delete the default loop task, we don't need it
}

void loop() {
    // Never gets called, we delete the loop task in setup() after creating the
    // UART task
}
