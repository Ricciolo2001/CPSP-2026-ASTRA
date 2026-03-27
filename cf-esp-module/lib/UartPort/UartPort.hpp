#ifndef UART_PORT_H
#define UART_PORT_H

#include <cstddef>
#include <cstdint>
#include <string_view>

#include <driver/uart.h>
#include <freertos/FreeRTOS.h>

// Thin RAII wrapper around the ESP-IDF UART C primitives.
// Responsible only for hardware configuration, driver lifecycle, and raw I/O.
class UartPort {
  public:
    struct Config {
        uart_port_t port;
        int rxBufferSize;
        int txBufferSize;
        uart_config_t uart;
        int txdPin = UART_PIN_NO_CHANGE;
        int rxdPin = UART_PIN_NO_CHANGE;
        int rtsPin = UART_PIN_NO_CHANGE;
        int ctsPin = UART_PIN_NO_CHANGE;
    };

    explicit UartPort(const Config &config);
    ~UartPort();

    /// Read up to maxLen bytes into buf; blocks for at most timeout ticks.
    /// Returns the number of bytes read, or -1 on error.
    int read(uint8_t *buf, size_t maxLen, TickType_t timeout);
    /// Overload of read() that blocks indefinitely until data is available.
    int read(uint8_t *buf, size_t maxLen) {
        return read(buf, maxLen, portMAX_DELAY);
    }

    /// Write len bytes from data to the UART TX.
    int write(const void *data, size_t len);
    /// Write a string to the UART TX.
    int write(std::string_view str) { return write(str.data(), str.size()); }

    /// Write data followed by a newline.
    void writeln(const void *data, size_t len) {
        write(data, len);
        write("\n", 1);
    }
    void writeln(std::string_view str) {
        write(str.data(), str.size());
        write("\n", 1);
    }

  private:
    Config config_;

    /// True if the UART driver has been installed.
    bool initialized_ = false;

    // Install the UART driver and configure pins. Returns false on failure.
    bool init();
    // Uninstall the UART driver and release resources.
    void deinit();
};

#endif // UART_PORT_H
