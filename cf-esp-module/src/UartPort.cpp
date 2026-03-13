#include "UartPort.h"

#include <Arduino.h>
#include <cstring>

UartPort::UartPort(const Config &config)
    : config_(config), initialized_(false) {}

UartPort::~UartPort() { deinit(); }

bool UartPort::init() {
    Serial.println("UART: Initializing hardware...");

    if (uart_driver_install(config_.port, kBufSize * 2, 0, 0, NULL, 0) !=
        ESP_OK) {
        Serial.println("UART: Failed to install driver");
        return false;
    }

    if (uart_param_config(config_.port, &config_.uart) != ESP_OK) {
        Serial.println("UART: Failed to configure parameters");
        return false;
    }

    if (uart_set_pin(config_.port, config_.txdPin, config_.rxdPin,
                     config_.rtsPin, config_.ctsPin) != ESP_OK) {
        Serial.println("UART: Failed to set pins");
        return false;
    }

    Serial.println("UART: Driver installed successfully.");
    initialized_ = true;
    return true;
}

void UartPort::deinit() {
    if (!initialized_) {
        return;
    }
    uart_driver_delete(config_.port);
    initialized_ = false;
}

int UartPort::read(uint8_t *buf, size_t maxLen, TickType_t timeout) {
    return uart_read_bytes(config_.port, buf, maxLen, timeout);
}

void UartPort::write(const void *data, size_t len) {
    uart_write_bytes(config_.port, data, len);
}
