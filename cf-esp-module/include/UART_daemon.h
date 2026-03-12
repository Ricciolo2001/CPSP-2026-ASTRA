#ifndef UART_DAEMON_H
#define UART_DAEMON_H

#include <driver/uart.h>
#include "BLE_manager.h"
#include "cJSON.h"

#define TXD_PIN (5)                  // UART TX pin
#define RXD_PIN (6)                  // UART RX pin
#define RTS_PIN (UART_PIN_NO_CHANGE) // UART RTS pin (not used)
#define CTS_PIN (UART_PIN_NO_CHANGE) // UART CTS pin (not used)

class UartDaemon
{
public:
    UartDaemon(uart_port_t port, int baudrate, BleManager *ble);
    ~UartDaemon();

    void start(uint32_t stackSize = 4096, UBaseType_t priority = 10);
    void stop();
    void reset();

private:
    uart_port_t _port;
    int _baudrate;
    BleManager *_ble;
    TaskHandle_t _taskHandle; // Riferimento per gestire la task

    // Buffer per la ricezione
    static const int BUF_SIZE = 1024;
    uint8_t *_dataBuffer;

    // Metodi interni
    bool init(); // Configurazione hardware
    void run();  // Loop infinito

    static void taskWrapper(void *arg)
    {
        UartDaemon *instance = static_cast<UartDaemon *>(arg);
        if (instance->init())
        { // Se l'init fallisce, non entriamo nel loop
            instance->run();
        }
        // Se run() esce, cancelliamo la task in sicurezza
        instance->stop();
    }
};

#endif