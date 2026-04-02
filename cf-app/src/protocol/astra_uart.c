// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 Eyad Issa <eyadlorenzo@gmail.com>

#include "astra_uart.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "astra_codec.h"
#include "transport/uart_framing.h"

#include "FreeRTOS.h" // IWYU pragma: keep
#include "portmacro.h"
#include "queue.h"
#include "task.h"
#include "uart2.h"

#define DEBUG_MODULE "ASTRA_UART"
#include "debug.h"

/* -------------------------------------------------------------------------
 * Internal constants
 * ---------------------------------------------------------------------- */

/** Number of packets that fit in the TX / RX queues. */
#define TX_QUEUE_LEN 8U
#define RX_QUEUE_LEN 8U

/** Task stack depth in words (x4 bytes on 32-bit targets). */
#define TASK_STACK_WORDS 256U

/** FreeRTOS priority for both UART tasks. */
#define TASK_PRIORITY 1U

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
 * Module state
 * ---------------------------------------------------------------------- */

static QueueHandle_t s_tx_queue;
static QueueHandle_t s_rx_queue;
static TaskHandle_t s_tx_task_handle;
static TaskHandle_t s_rx_task_handle;
static bool s_initialized = false;

/* -------------------------------------------------------------------------
 * Internal tasks
 * ---------------------------------------------------------------------- */

static void uart_tx_task(void *params) {
  (void)params;

  uint8_t raw_buf[RAW_BUF_SIZE];
  uint8_t frame_buf[FRAME_BUF_SIZE];
  uint8_t scratch[UART_FRAMING_SCRATCH_SIZE(RAW_BUF_SIZE)];

  while (true) {
    astra_uart_packet_t packet;
    if (xQueueReceive(s_tx_queue, &packet, portMAX_DELAY) != pdTRUE) {
      continue;
    }

    size_t raw_len = 0;
    if (!astra_uart_serialize(&packet, raw_buf, sizeof(raw_buf), &raw_len)) {
      DEBUG_PRINT("TX: serialize failed (type=0x%02x)\n", (unsigned)packet.type);
      continue;
    }

    size_t frame_len = uart_frame_encode(raw_buf, raw_len, scratch, sizeof(scratch), frame_buf, sizeof(frame_buf));
    if (frame_len == 0U) {
      DEBUG_PRINT("TX: frame encode failed\n");
      continue;
    }

    uart2SendData((uint32_t)frame_len, frame_buf);
  }
}

/**
 * @brief Reads bytes from UART into @p out_buf until the @p delimiter is found or @p max_len is reached.
 */
static ssize_t read_until_char(uint8_t delimiter, uint8_t *out_buf, size_t max_len) {
  size_t idx = 0;
  while (idx < max_len) {
    uint8_t byte;
    int result = uart2GetData(1, &byte);
    if (result <= 0) {
      return -1; /* error or no data */
    }
    if (byte == delimiter) {
      return (ssize_t)idx; /* return length of data read, excluding delimiter */
    }
    out_buf[idx++] = byte;
  }
  return -1; /* buffer overflow without finding delimiter */
}

static void uart_rx_task(void *params) {
  (void)params;

  uint8_t frame_buf[FRAME_BUF_SIZE];
  uint8_t raw_buf[RAW_BUF_SIZE];
  uint8_t scratch[UART_FRAMING_SCRATCH_SIZE(RAW_BUF_SIZE)];

  while (true) {
    // Read until the 0x00 delimiter (delimiter is consumed but not stored in frame_buf)
    int received = read_until_char(0x00, frame_buf, sizeof(frame_buf));
    if (received <= 0) {
      DEBUG_PRINT("RX: uart2GetData failed or returned no data\n");
      continue;
    }
    /* uart_frame_decode expects frame_len to include the trailing 0x00
     * delimiter, but read_until_char strips it and does not count it.
     * Add 1 to restore the expected length. */
    size_t frame_len = (size_t)received + 1U;

    DEBUG_PRINT("RX: received %d bytes\n", received);

    size_t raw_len = 0;
    if (!uart_frame_decode(frame_buf, frame_len, scratch, sizeof(scratch), raw_buf, sizeof(raw_buf), &raw_len)) {
      DEBUG_PRINT("RX: frame decode / CRC check failed\n");
      continue;
    }

    astra_uart_packet_t packet;
    if (!astra_uart_deserialize(raw_buf, raw_len, &packet)) {
      DEBUG_PRINT("RX: deserialize failed\n");
      continue;
    }

    if (xQueueSend(s_rx_queue, &packet, 0) != pdTRUE) {
      DEBUG_PRINT("RX: queue full, packet dropped (type=0x%02x)\n", (unsigned)packet.type);
    }
  }
}

/* -------------------------------------------------------------------------
 * Lifecycle
 * ---------------------------------------------------------------------- */

bool astra_uart_init(void) {
  if (s_initialized) {
    return true; /* idempotent */
  }

  s_tx_queue = xQueueCreate(TX_QUEUE_LEN, sizeof(astra_uart_packet_t));
  s_rx_queue = xQueueCreate(RX_QUEUE_LEN, sizeof(astra_uart_packet_t));

  if (s_tx_queue == NULL || s_rx_queue == NULL) {
    DEBUG_PRINT("Failed to create UART queues\n");
    goto cleanup;
  }

  BaseType_t tx_ok =
      xTaskCreate(uart_tx_task, "astra_uart_tx", TASK_STACK_WORDS, NULL, TASK_PRIORITY, &s_tx_task_handle);
  BaseType_t rx_ok =
      xTaskCreate(uart_rx_task, "astra_uart_rx", TASK_STACK_WORDS, NULL, TASK_PRIORITY, &s_rx_task_handle);

  if (tx_ok != pdPASS || rx_ok != pdPASS) {
    DEBUG_PRINT("Failed to create UART tasks\n");
    goto cleanup;
  }

  s_initialized = true;
  return true;

cleanup:
  if (s_tx_queue != NULL) {
    vQueueDelete(s_tx_queue);
    s_tx_queue = NULL;
  }
  if (s_rx_queue != NULL) {
    vQueueDelete(s_rx_queue);
    s_rx_queue = NULL;
  }
  if (s_tx_task_handle != NULL) {
    vTaskDelete(s_tx_task_handle);
    s_tx_task_handle = NULL;
  }
  if (s_rx_task_handle != NULL) {
    vTaskDelete(s_rx_task_handle);
    s_rx_task_handle = NULL;
  }
  return false;
}

/* -------------------------------------------------------------------------
 * Public API
 * ---------------------------------------------------------------------- */

BaseType_t astra_uart_send(const astra_uart_packet_t *packet, TickType_t timeout) {
  assert(s_initialized && "astra_uart_send called before astra_uart_init");
  assert(packet != NULL && "packet must not be NULL");
  return xQueueSend(s_tx_queue, packet, timeout);
}

BaseType_t astra_uart_receive(astra_uart_packet_t *out_packet, TickType_t timeout) {
  assert(s_initialized && "astra_uart_receive called before astra_uart_init");
  assert(out_packet != NULL && "out_packet must not be NULL");
  return xQueueReceive(s_rx_queue, out_packet, timeout);
}
