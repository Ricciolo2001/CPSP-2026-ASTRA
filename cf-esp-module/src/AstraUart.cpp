// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 Eyad Issa
// SPDX-FileCopyrightText: 2026 Alessandro Armandi

#include "AstraUart.hpp"

#include "Arduino.h"
#include <driver/uart.h>
#include <freertos/FreeRTOS.h>
#include <string.h>

extern "C" {
#include "protocol/astra_codec.h"
#include "transport/uart_framing.h"
}

/* -------------------------------------------------------------------------
 * Internal constants
 * ---------------------------------------------------------------------- */

/**
 * Raw (serialized, un-framed) buffer: 1-byte type tag + largest payload.
 * sizeof(astra_uart_rssi_value_t) == 7, so 64 bytes is generous.
 */
#define RAW_BUF_SIZE 64U

/**
 * Framed buffer: RAW_BUF_SIZE + COBS overhead (1) + CRC16 (2) + delimiter (1).
 * 128 bytes is well above the maximum frame length for current packet types.
 */
#define FRAME_BUF_SIZE 128U

/* -------------------------------------------------------------------------
 * Public send / receive API
 * ---------------------------------------------------------------------- */

BaseType_t AstraUart::send(const astra_uart_packet_t &packet) {
    uint8_t raw_buf[RAW_BUF_SIZE];
    uint8_t frame_buf[FRAME_BUF_SIZE];
    uint8_t scratch[UART_FRAMING_SCRATCH_SIZE(RAW_BUF_SIZE)];

    size_t raw_len = 0;
    if (!astra_uart_serialize(&packet, raw_buf, sizeof(raw_buf), &raw_len)) {
        return pdFALSE;
    }

    size_t frame_len =
        uart_frame_encode(raw_buf, raw_len, scratch, sizeof(scratch), frame_buf,
                          sizeof(frame_buf));
    if (frame_len == 0U) {
        return pdFALSE;
    }

    int written = uart_port_.write(frame_buf, frame_len);
    return (written == (int)frame_len) ? pdTRUE : pdFALSE;
}

namespace {
void print_raw_bytes(const uint8_t *data, size_t len) {
    Serial.print("Raw bytes: ");
    for (size_t i = 0; i < len; ++i) {
        Serial.printf("%02x ", data[i]);
    }
    Serial.println();
}

} // namespace

BaseType_t AstraUart::receive(astra_uart_packet_t &out_packet,
                              TickType_t timeout) {
    uint8_t frame_buf[FRAME_BUF_SIZE];
    uint8_t raw_buf[RAW_BUF_SIZE];
    uint8_t scratch[UART_FRAMING_SCRATCH_SIZE(RAW_BUF_SIZE)];

    int received =
        (int)read_until_delimiter(frame_buf, sizeof(frame_buf), timeout);
    if (received <= 0) {
        return pdFALSE;
    }

    size_t frame_len = (size_t)received;

    size_t raw_len = 0;
    if (!uart_frame_decode(frame_buf, frame_len, scratch, sizeof(scratch),
                           raw_buf, sizeof(raw_buf), &raw_len)) {
        Serial.println("Failed to decode UART frame");
        print_raw_bytes(frame_buf, frame_len);
        return pdFALSE;
    }

    if (!astra_uart_deserialize(raw_buf, raw_len, &out_packet)) {
        Serial.println("Failed to deserialize UART packet");
        print_raw_bytes(raw_buf, raw_len);
        return pdFALSE;
    }

    return pdTRUE;
}

constexpr uint8_t astra_pkt_delimiter = '\x00';

uint32_t AstraUart::read_until_delimiter(uint8_t *buf, size_t max_len,
                                         TickType_t timeout) {
    size_t idx = 0;
    TickType_t start_tick = xTaskGetTickCount();

    while (idx < max_len) {
        // Calculate remaining time in our "budget"
        TickType_t elapsed = xTaskGetTickCount() - start_tick;
        if (elapsed >= timeout) {
            break;
        }
        TickType_t remaining = timeout - elapsed;

        // Read a single byte
        int read = uart_port_.read(buf + idx, 1, remaining);

        if (read < 0) {
            return 0; // Hardware/Driver Error
        } else if (read == 0) {
            break; // Individual byte read timed out
        }

        // We successfully read a byte, so increment the index
        idx++;

        // Check if the byte we JUST read (at idx-1) is the delimiter
        if (buf[idx - 1] == (uint8_t)astra_pkt_delimiter) {
            return idx; // Found delimiter, return count including it
        }
    }

    return idx; // Return bytes read (timeout or buffer full)
}
