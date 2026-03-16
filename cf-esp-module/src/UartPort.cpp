#include "UartPort.h"

#include <cstring>
#include <esp_err.h>
#include <esp_log.h>
#include <stdexcept>
#include <string_view>

#define TAG "UartPort"

UartPort::UartPort(const Config &config) : config_(config) {
    if (!init()) {
        throw std::runtime_error("Failed to initialize UART port");
    }
}

UartPort::~UartPort() { deinit(); }

bool UartPort::init() {

    if (uart_driver_install(config_.port, config_.rxBufferSize,
                             config_.txBufferSize, 0, NULL, 0) != ESP_OK) {
        ESP_LOGI(TAG, "Failed to install UART driver");
        return false;
    }

    if (uart_param_config(config_.port, &config_.uart) != ESP_OK) {
        ESP_LOGI(TAG, "Failed to configure UART parameters");
        uart_driver_delete(config_.port);
        return false;
    }

    if (uart_set_pin(config_.port, config_.txdPin, config_.rxdPin,
                     config_.rtsPin, config_.ctsPin) != ESP_OK) {
        ESP_LOGI(TAG, "Failed to set UART pins");
        uart_driver_delete(config_.port);
        return false;
    }

    initialized_ = true;
    return true;
}

void UartPort::deinit() {
    if (!initialized_) {
        return; // Nothing to do
    }
    uart_driver_delete(config_.port);
    initialized_ = false;
}

int UartPort::read(uint8_t *buf, size_t maxLen, TickType_t timeout) {
    assert(buf != nullptr);
    return uart_read_bytes(config_.port, buf, maxLen, timeout);
}

int UartPort::write(const void *data, size_t len) {
    assert(data != nullptr);
    return uart_write_bytes(config_.port, data, len);
}
