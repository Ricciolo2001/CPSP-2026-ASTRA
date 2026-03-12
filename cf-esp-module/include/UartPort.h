#ifndef UART_PORT_H
#define UART_PORT_H

#include <cstddef>
#include <cstdint>
#include <driver/uart.h>
#include <freertos/FreeRTOS.h>

// Thin RAII wrapper around the ESP-IDF UART C primitives.
// Responsible only for hardware configuration, driver lifecycle, and raw I/O.
class UartPort {
  public:
    static constexpr int kBufSize = 1024;

    struct Config {
        uart_port_t port = UART_NUM_1;
        uart_config_t uart = {
            .baud_rate = 115200,
            .data_bits = UART_DATA_8_BITS,
            .parity = UART_PARITY_DISABLE,
            .stop_bits = UART_STOP_BITS_1,
            .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        };
        int txdPin = 5;
        int rxdPin = 6;
        int rtsPin = UART_PIN_NO_CHANGE;
        int ctsPin = UART_PIN_NO_CHANGE;
    };

    explicit UartPort(const Config &config);
    ~UartPort();

    // Install the UART driver and configure pins. Returns false on failure.
    bool init();
    // Uninstall the UART driver (idempotent).
    void deinit();

    // Read up to maxLen bytes into buf; blocks for at most timeout ticks.
    // Returns the number of bytes read, or -1 on error.
    int read(uint8_t *buf, size_t maxLen, TickType_t timeout);

    // Write len bytes from data to the UART TX.
    void write(const void *data, size_t len);
    // Write a null-terminated string to the UART TX.
    void write(const char *str);

  private:
    Config config_;
    bool initialized_;
};

#endif // UART_PORT_H
