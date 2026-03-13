#ifndef UART_DAEMON_H
#define UART_DAEMON_H

#include <memory>
#include <string>

#include "BleManager.h"
#include "freertos/task.hpp"
#include "UartPort.h"

// High-level UART daemon: owns the FreeRTOS task, implements the text-based
// line protocol, and dispatches commands to BleManager.
// All hardware I/O is delegated to UartPort.
class UartDaemon : public freertos::Task<UartDaemon> {
    friend class freertos::Task<UartDaemon>;

  public:
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
        uint32_t taskStackSize = 4096;
        UBaseType_t taskPriority = 10;
    };

    explicit UartDaemon(const Config &config, BleManager *ble);
    ~UartDaemon();

  private:
    UartPort uart_;
    BleManager *ble_;

    std::unique_ptr<uint8_t[]> dataBuffer_;

    bool init();
    void run();
    void executeCommand(const std::string &command, const std::string &args);
};

#endif // UART_DAEMON_H
