#pragma once

#include "UartPort.hpp"

extern "C" {
#include "protocol/astra_proto.h"
}

/// High-level ASTRA UART interface
///
/// This class provides methods to send and receive ASTRA UART packets
/// (`astra_uart_packet_t`) over a configured UART port.
///
/// It handles serialization, framing, and error checking internally, exposing a
/// simple API for sending and receiving structured packets.
class AstraUart {
  public:
    explicit AstraUart(UartPort::Config config) : uart_port_(config) {};
    ~AstraUart() = default;

    /// Send a packet over UART.
    /// Blocks until the packet is inserted into the UART driver's TX buffer.
    /// @returns pdTRUE on success.
    BaseType_t send(const astra_uart_packet_t &message);

    /// Receive a packet, blocking for at most `timeout` ticks.
    /// @returns pdTRUE if a packet was successfully received and deserialized
    /// into `out_packet`. Returns pdFALSE on timeout or any error (e.g.
    /// framing, decoding, deserialization).
    BaseType_t receive(astra_uart_packet_t &out_packet,
                       TickType_t timeout = portMAX_DELAY);

  private:
    UartPort uart_port_;

    uint32_t read_until_delimiter(uint8_t *buf, size_t max_len,
                                  TickType_t timeout);
};
