#ifndef UART_DAEMON_H
#define UART_DAEMON_H

#include <driver/uart.h>

#include "BleManager.h"

#define UART_TXD_PIN (5)                  // UART TX pin
#define UART_RXD_PIN (6)                  // UART RX pin
#define UART_RTS_PIN (UART_PIN_NO_CHANGE) // UART RTS pin (not used)
#define UART_CTS_PIN (UART_PIN_NO_CHANGE) // UART CTS pin (not used)

class UartDaemon {
  public:
    explicit UartDaemon(uart_port_t port, int baudrate, BleManager *ble);
    ~UartDaemon();

    void start(uint32_t stackSize = 4096, UBaseType_t priority = 10);
    void stop();
    void reset();

  private:
    uart_port_t port_;
    int baudrate_;
    BleManager *ble_;
    TaskHandle_t taskHandle_; // Riferimento per gestire la task

    // Buffer per la ricezione
    static const int kBufSize = 1024;
    uint8_t *dataBuffer_;

    // Metodi interni
    bool init(); // Configurazione hardware
    void run();  // Loop infinito

    static void taskWrapper(void *arg);
};

#endif // UART_DAEMON_H
