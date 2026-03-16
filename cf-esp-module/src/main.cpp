#include <optional>
#include <stdio.h>
#include <stdlib.h>

#include <Arduino.h>
#include <driver/gpio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <sdkconfig.h>

#include "BleManager.h"
#include "UartDaemon.h"

static std::optional<UartDaemon> uartDaemon;

void setup() {
    Serial.begin(115200);
    delay(1000); // Better safe than sorry?
    Serial.println("Serial monitor setup complete.");

    // BLE initial setup
    BleManager &ble = BleManager::instance();
    ble.startBackgroundScan();

    Serial.println("BLE Manager initialized, background scan running.");

    pinMode(BUILTIN_LED, OUTPUT);
    digitalWrite(BUILTIN_LED, HIGH); // LOW turns the LED on, HIGH turns it off
    // like who designed that?

    auto config = UartDaemon::Config{
        UartPort::Config{
            UART_NUM_1,
            2048, // TX buffer size
            2048, // RX buffer size
            {
                115200,                   // Baudrate
                UART_DATA_8_BITS,         // Byte size
                UART_PARITY_DISABLE,      // Parity mode
                UART_STOP_BITS_1,         // Stop bits
                UART_HW_FLOWCTRL_DISABLE, // Flow control
            },
            GPIO_NUM_5, // TX pin
            GPIO_NUM_6, // RX pin
        },
        4096, // Task stack size
        10,   // Task priority
    };

    uartDaemon.emplace(config, ble);
    uartDaemon->start();

    vTaskDelete(NULL); // Delete the default loop task, we don't need it
}

void loop() {
    // Never gets called, we delete the loop task in setup() after creating the
    // UART task
}
