#pragma once

#include "BleManager.h"

struct UartTaskParams {
    uart_port_t port;
    int baudrate;
    BleManager *ble;
};
