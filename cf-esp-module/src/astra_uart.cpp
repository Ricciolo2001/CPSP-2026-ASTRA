#include "astra_uart.hpp"

#include <driver/uart.h>
#include <freertos/FreeRTOS.h>
#include <string.h>

#include "uart_framing.h"

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

namespace {
/* -------------------------------------------------------------------------
 * Serialization / deserialization
 * ---------------------------------------------------------------------- */

bool astra_uart_serialize(const astra_uart_packet_t *packet, uint8_t *out_buf,
                          size_t out_max, size_t *out_len) {
    if (packet == NULL || out_buf == NULL || out_len == NULL) {
        return false;
    }

    /* Resolve the payload size for this packet type up-front so that we only
     * need a single bounds check before writing anything to out_buf. */
    size_t payload_size;
    switch ((astra_uart_packet_type_t)packet->type) {
    case ASTRA_UART_BIND_REQUEST:
        payload_size = sizeof(packet->payload.bind_request);
        break;
    case ASTRA_UART_BIND_RESPONSE:
        payload_size = sizeof(packet->payload.bind_response);
        break;
    case ASTRA_UART_RSSI_VALUE:
        payload_size = sizeof(packet->payload.rssi_value);
        break;
    case ASTRA_UART_UNBIND_REQUEST:
        payload_size = 0U;
        break;
    case ASTRA_UART_UNBIND_RESPONSE:
        payload_size = sizeof(packet->payload.bind_response);
        break;
    default:
        return false; /* unknown / unimplemented packet type */
    }

    size_t total = 1U /* type tag */ + payload_size;
    if (total > out_max) {
        return false;
    }

    out_buf[0] = packet->type;

    switch ((astra_uart_packet_type_t)packet->type) {
    case ASTRA_UART_BIND_REQUEST:
        memcpy(&out_buf[1], &packet->payload.bind_request, payload_size);
        break;
    case ASTRA_UART_BIND_RESPONSE:
        memcpy(&out_buf[1], &packet->payload.bind_response, payload_size);
        break;
    case ASTRA_UART_RSSI_VALUE:
        memcpy(&out_buf[1], &packet->payload.rssi_value, payload_size);
        break;
    case ASTRA_UART_UNBIND_REQUEST:
        /* no payload */
        break;
    case ASTRA_UART_UNBIND_RESPONSE:
        memcpy(&out_buf[1], &packet->payload.bind_response, payload_size);
        break;
    default:
        return false;
    }

    *out_len = total;
    return true;
}

bool astra_uart_deserialize(const uint8_t *data, size_t data_len,
                            astra_uart_packet_t *out_packet) {
    if (data == NULL || out_packet == NULL) {
        return false;
    }

    if (data_len < 1U) {
        return false; /* need at least the type tag */
    }

    out_packet->type = data[0];

    const uint8_t *payload_data = data + 1;
    size_t payload_len = data_len - 1U;

    switch ((astra_uart_packet_type_t)out_packet->type) {
    case ASTRA_UART_BIND_REQUEST:
        if (payload_len != sizeof(out_packet->payload.bind_request)) {
            return false;
        }
        memcpy(&out_packet->payload.bind_request, payload_data, payload_len);
        break;
    case ASTRA_UART_BIND_RESPONSE:
        if (payload_len != sizeof(out_packet->payload.bind_response)) {
            return false;
        }
        memcpy(&out_packet->payload.bind_response, payload_data, payload_len);
        break;
    case ASTRA_UART_RSSI_VALUE:
        if (payload_len != sizeof(out_packet->payload.rssi_value)) {
            return false;
        }
        memcpy(&out_packet->payload.rssi_value, payload_data, payload_len);
        break;
    case ASTRA_UART_UNBIND_REQUEST:
        if (payload_len != 0U) {
            return false;
        }
        break;
    case ASTRA_UART_UNBIND_RESPONSE:
        if (payload_len != sizeof(out_packet->payload.bind_response)) {
            return false;
        }
        memcpy(&out_packet->payload.bind_response, payload_data, payload_len);
        break;
    default:
        return false; /* unknown / unimplemented packet type */
    }

    return true;
}

} // namespace

/* -------------------------------------------------------------------------
 * Public send / receive API
 * ---------------------------------------------------------------------- */

BaseType_t AstraUart::send(const astra_uart_packet_t *packet,
                           TickType_t timeout) {
    (void)timeout;
    assert(packet != nullptr && "packet must not be NULL");

    uint8_t raw_buf[RAW_BUF_SIZE];
    uint8_t frame_buf[FRAME_BUF_SIZE];

    size_t raw_len = 0;
    if (!astra_uart_serialize(packet, raw_buf, sizeof(raw_buf), &raw_len)) {
        return pdFALSE;
    }

    size_t frame_len =
        uart_frame_encode(raw_buf, raw_len, frame_buf, sizeof(frame_buf));
    if (frame_len == 0U) {
        return pdFALSE;
    }

    int written = uart_port_.write(frame_buf, frame_len);
    return (written == (int)frame_len) ? pdTRUE : pdFALSE;
}

BaseType_t AstraUart::receive(astra_uart_packet_t *out_packet,
                              TickType_t timeout) {
    assert(out_packet != nullptr && "out_packet must not be NULL");

    uint8_t frame_buf[FRAME_BUF_SIZE];
    uint8_t raw_buf[RAW_BUF_SIZE];

    int received = uart_port_.read(frame_buf, sizeof(frame_buf), timeout);
    if (received <= 0) {
        return pdFALSE;
    }
    size_t frame_len = (size_t)received;

    size_t raw_len = 0;
    if (!uart_frame_decode(frame_buf, frame_len, raw_buf, sizeof(raw_buf),
                           &raw_len)) {
        return pdFALSE;
    }

    if (!astra_uart_deserialize(raw_buf, raw_len, out_packet)) {
        return pdFALSE;
    }

    return pdTRUE;
}