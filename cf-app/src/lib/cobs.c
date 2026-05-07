// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 Eyad Issa

#include "cobs.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define COBS_MAX_BLOCK_SIZE 254

cobs_status_t cobs_encode(const uint8_t *restrict src, size_t src_len, uint8_t *restrict dst, size_t dst_max,
                          size_t *out_len) {

  uint8_t *dst_start = dst;
  uint8_t *code_ptr = dst++; // Reserve first byte for the code
  uint8_t code = 0x01;

  for (size_t i = 0; i < src_len; i++) {
    // Check for buffer overflow before writing
    if ((size_t)(dst - dst_start) >= dst_max) {
      return COBS_RET_ERR_BUFFER_OVERFLOW;
    }

    if (src[i] != 0x00) {
      *dst++ = src[i];
      code++;
    }

    if (src[i] == 0x00 || code == 0xFF) {
      *code_ptr = code;
      code = 0x01;
      code_ptr = dst++;
      // Check overflow for the next code byte reservation
      if (i < src_len - 1 && (size_t)(dst - dst_start) >= dst_max) {
        return COBS_RET_ERR_BUFFER_OVERFLOW;
      }
    }
  }

  *code_ptr = code;
  if (out_len) {
    *out_len = (size_t)(dst - dst_start);
  }
  return COBS_RET_OK;
}

cobs_status_t cobs_decode(const uint8_t *restrict src, size_t src_len, uint8_t *restrict dst, size_t dst_max,
                          size_t *out_len) {

  const uint8_t *src_end = src + src_len;
  uint8_t *dst_start = dst;

  while (src < src_end) {
    uint8_t code = *src++;

    // Copy (code - 1) bytes
    for (uint8_t i = 1; i < code; i++) {
      if (src >= src_end) {
        return COBS_RET_ERR_BAD_PAYLOAD;
      }
      if ((size_t)(dst - dst_start) >= dst_max) {
        return COBS_RET_ERR_BUFFER_OVERFLOW;
      }
      *dst++ = *src++;
    }

    // Add back the zero unless it's the end or a max-block filler
    if (code < 0xFF && src < src_end) {
      if ((size_t)(dst - dst_start) >= dst_max) {
        return COBS_RET_ERR_BUFFER_OVERFLOW;
      }
      *dst++ = 0x00;
    }
  }

  if (out_len) {
    *out_len = (size_t)(dst - dst_start);
  }
  return COBS_RET_OK;
}
