#pragma once

extern "C" {
#include "astra_protocol.h"
};

#include "UartPort.h"

class AstraUart {
  public:
    explicit AstraUart(UartPort::Config config) : uart_port_(config) {};
    ~AstraUart() = default;

    BaseType_t send(const astra_uart_packet_t *message,
                    TickType_t timeout = portMAX_DELAY);
    BaseType_t receive(astra_uart_packet_t *message,
                       TickType_t timeout = portMAX_DELAY);

  private:
    UartPort uart_port_;

    uint32_t read_until_delimiter(uint8_t *buf, size_t max_len, TickType_t timeout);
};
