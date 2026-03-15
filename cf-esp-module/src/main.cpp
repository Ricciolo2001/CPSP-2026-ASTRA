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
    ble.init();
    ble.startBackgroundScan();

    Serial.println("BLE Manager initialized, background scan running.");

    pinMode(BUILTIN_LED, OUTPUT);
    digitalWrite(BUILTIN_LED, HIGH); // LOW turns the LED on, HIGH turns it off
    // like who designed that?

    uartDaemon.emplace(UartDaemon::Config{}, &ble);
    uartDaemon->start();

    vTaskDelete(NULL); // Delete the default loop task, we don't need it
}

void loop() {
    // Never gets called, we delete the loop task in setup() after creating the
    // UART task
}
