// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 Eyad Issa

#pragma once

#include <stddef.h>
#include <stdint.h>

/**
 * @brief CRC16 context
 * Opaque object containing the current state of the calculation.
 */
typedef struct {
  uint16_t remainder;
} crc16_ctx_t;

/**
 * @brief Initialize CRC16 context to 0xFFFF
 */
void crc16_init(crc16_ctx_t *ctx);

/**
 * @brief Update checksum with new data (Streaming)
 */
void crc16_update(crc16_ctx_t *ctx, const void *data, size_t size);

/**
 * @brief Returns the final CRC16 checksum
 */
uint16_t crc16_finalize(const crc16_ctx_t *ctx);

/**
 * @brief Convenience function for one-shot calculation
 */
uint16_t crc16_compute(const void *data, size_t size);
