#ifndef UART_DAEMON_H
#define UART_DAEMON_H

#include <cstddef>
#include <driver/uart.h>
#include <memory>

#include "BleManager.h"

#define UART_TXD_PIN (5)                  // UART TX pin
#define UART_RXD_PIN (6)                  // UART RX pin
#define UART_RTS_PIN (UART_PIN_NO_CHANGE) // UART RTS pin (not used)
#define UART_CTS_PIN (UART_PIN_NO_CHANGE) // UART CTS pin (not used)

class UartDaemon {
  public:
    explicit UartDaemon(uart_port_t port, int baudrate, BleManager *ble);
    ~UartDaemon();

    // Start the UART daemon task
    void start(uint32_t stackSize = 4096, UBaseType_t priority = 10);
    // Stop the UART daemon task
    void stop();
    // Reset the UART daemon (stop + start)
    void reset();

  private:
    uart_port_t port_;
    int baudrate_;
    BleManager *ble_;
    TaskHandle_t taskHandle_; // Riferimento per gestire la task

    // Buffer per la ricezione
    static constexpr int kBufSize = 1024;
    std::unique_ptr<uint8_t[]> dataBuffer_;

    // Metodi interni
    bool init(); // Configurazione hardware
    void run();  // Loop infinito

    static void taskWrapper(void *arg);
    void executeCommand(const std::string &command, const std::string &args);
};

#endif // UART_DAEMON_H
