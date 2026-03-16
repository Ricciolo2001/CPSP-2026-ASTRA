#ifndef UART_DAEMON_H
#define UART_DAEMON_H

#include <memory>
#include <string>

#include "BleManager.h"
#include "UartPort.h"
#include "freertos/task.hpp"

// High-level UART daemon: owns the FreeRTOS task, implements the text-based
// line protocol, and dispatches commands to BleManager.
// All hardware I/O is delegated to UartPort.
class UartDaemon : public freertos::Task<UartDaemon> {
    friend class freertos::Task<UartDaemon>;

  public:
    struct Config {
        UartPort::Config uartConfig;
        uint32_t taskStackSize = 4096;
        UBaseType_t taskPriority = 10;
    };

    explicit UartDaemon(const Config &config, BleManager &ble);
    ~UartDaemon();

  private:
    static constexpr int kBufSize = 1024;

    UartPort uart_;
    BleManager &ble_;

    std::unique_ptr<uint8_t[]> dataBuffer_;

    void run();
    void executeCommand(const std::string &command, const std::string &args);
};

#endif // UART_DAEMON_H
