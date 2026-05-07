// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 Eyad Issa

#pragma once

/**
 * cobs.h - Consistent Overhead Byte Stuffing (COBS)
 * Encoding and decoding functions.
 */

#include <stddef.h>
#include <stdint.h>

typedef enum {
  COBS_RET_OK = 0,
  COBS_RET_ERR_BAD_PAYLOAD,
  COBS_RET_ERR_BUFFER_OVERFLOW,
} cobs_status_t;

/**
 * @brief Encodes data using COBS with bounds checking.
 * @param src Pointer to raw data.
 * @param src_len Length of raw data.
 * @param dst Pointer to destination buffer.
 * @param dst_max Max size of destination buffer.
 * @param out_len Pointer to store the resulting encoded length.
 */
cobs_status_t cobs_encode(const uint8_t *restrict src, size_t src_len, uint8_t *restrict dst, size_t dst_max,
                          size_t *out_len);

/**
 * @brief Decodes COBS data with bounds checking.
 */
cobs_status_t cobs_decode(const uint8_t *restrict src, size_t src_len, uint8_t *restrict dst, size_t dst_max,
                          size_t *out_len);
