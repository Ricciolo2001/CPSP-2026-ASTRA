#pragma once

/**
 * uart_framing.h - Generic UART packet framing (COBS + CRC16)
 *
 * Provides a transport-level framing layer for UART communication. Each frame
 * is structured as:
 *
 *   [ COBS-encoded( payload | CRC16_MSB | CRC16_LSB ) ] [ 0x00 delimiter ]
 *
 * This module is application-agnostic: it knows nothing about the content of
 * the payload, only how to protect and delimit it.
 *
 * Encoding pipeline (TX):
 *   raw payload  ->  append CRC16  ->  COBS encode  ->  append 0x00
 *
 * Decoding pipeline (RX):
 *   received bytes  ->  strip 0x00  ->  COBS decode  ->  verify CRC16
 *   ->  raw payload
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/**
 * Minimum scratch buffer size required by uart_frame_encode (pass payload_len)
 * or uart_frame_decode (pass out_max).  The +2 accounts for the two CRC bytes
 * that are appended to the payload before COBS encoding / stripped after
 * COBS decoding.
 */
#define UART_FRAMING_SCRATCH_SIZE(n) ((n) + 2U)

/**
 * @brief Encodes a raw payload into a framed UART packet.
 *
 * Appends a CRC16 checksum to @p payload, encodes the result with COBS, and
 * appends a 0x00 frame delimiter.  The entire output is written into @p
 * out_buf.
 *
 * @param payload      Pointer to the raw payload bytes.
 * @param payload_len  Length of the raw payload in bytes.
 * @param scratch      Caller-provided scratch buffer of at least
 *                     UART_FRAMING_SCRATCH_SIZE(payload_len) bytes.
 * @param scratch_size Size of @p scratch in bytes.
 * @param out_buf      Output buffer that will receive the framed packet.
 * @param out_max      Size of @p out_buf in bytes.
 *
 * @return Total number of bytes written to @p out_buf (including the 0x00
 *         delimiter), or 0 on error (e.g. scratch/output buffer too small,
 *         COBS encoding failure).
 */
size_t uart_frame_encode(const uint8_t *payload, size_t payload_len,
                         uint8_t *scratch, size_t scratch_size,
                         uint8_t *out_buf, size_t out_max);

/**
 * @brief Decodes a framed UART packet back into its raw payload.
 *
 * Strips the trailing 0x00 delimiter, COBS-decodes the data, and verifies the
 * embedded CRC16 checksum.  On success the verified payload is written into
 * @p out_payload and its length is stored in @p out_len.
 *
 * @param frame        Pointer to the received frame bytes (including the 0x00
 *                     delimiter as the last byte).
 * @param frame_len    Total length of @p frame in bytes (including delimiter).
 * @param scratch      Caller-provided scratch buffer of at least
 *                     UART_FRAMING_SCRATCH_SIZE(out_max) bytes.
 * @param scratch_size Size of @p scratch in bytes.
 * @param out_payload  Output buffer that will receive the decoded payload.
 * @param out_max      Size of @p out_payload in bytes.
 * @param out_len      Set to the number of decoded payload bytes on success.
 *
 * @return true if decoding and CRC verification succeeded, false otherwise.
 */
bool uart_frame_decode(const uint8_t *frame, size_t frame_len, uint8_t *scratch,
                       size_t scratch_size, uint8_t *out_payload,
                       size_t out_max, size_t *out_len);
