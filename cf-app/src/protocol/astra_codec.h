#pragma once

/**
 * @file astra_codec.h
 * @brief Serialization and deserialization of ASTRA UART packets.
 *
 * This module provides functions to convert between the in-memory
 * representation of ASTRA UART packets (astra_uart_packet_t) and
 * a flat byte format suitable for transmission over UART.
 *
 * Readers should not need to interact with this module directly,
 * as the higher-level astra_uart_send() and astra_uart_receive()
 * functions handle serialization and deserialization internally.
 */

#include "astra_proto.h"

#include <stdbool.h>
#include <stddef.h>

/**
 * @brief Compares two BLE addresses for equality.
 * @return 0 if equal, -1 if addr1 < addr2, 1 if addr1 > addr2 (same semantics as memcmp)
 */
int astra_dev_addr_cmp(const astra_dev_addr_t *addr1, const astra_dev_addr_t *addr2);

/**
 * @brief Serializes an astra_uart_packet_t into a flat byte buffer.
 *
 * The output buffer will contain a one-byte type tag followed by the packed
 * payload struct.  Only the fields relevant to @p packet->type are written.
 *
 * @param packet   Packet to serialize.
 * @param out_buf  Destination buffer.
 * @param out_max  Size of @p out_buf in bytes.
 * @param out_len  Set to the number of bytes written on success.
 *
 * @return true on success, false if the packet type is unknown or the buffer
 *         is too small.
 */
bool astra_uart_serialize(const astra_uart_packet_t *packet, uint8_t *out_buf, size_t out_max, size_t *out_len);

/**
 * @brief Deserializes a flat byte buffer into an astra_uart_packet_t.
 *
 * Expects the buffer to start with a one-byte type tag followed by the
 * matching packed payload struct.
 *
 * @param data        Source buffer.
 * @param data_len    Length of @p data in bytes.
 * @param out_packet  Populated on success.
 *
 * @return true on success, false if the type is unknown or @p data_len does
 *         not match the expected payload size.
 */
bool astra_uart_deserialize(const uint8_t *data, size_t data_len, astra_uart_packet_t *out_packet);
