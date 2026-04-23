// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 Eyad Issa <eyadlorenzo@gmail.com>

#pragma once

/**
 * @file astra_uart.h
 * @brief ASTRA UART protocol layer.
 *
 * This module implements the ASTRA UART protocol layer, which provides a
 * thread-safe API for sending and receiving ASTRA packets over UART.
 *
 * It manages FreeRTOS queues for outgoing and incoming packets and spawns
 * background tasks to handle UART transmission and reception.
 *
 * The higher-level ASTRA application code can use the astra_uart_send()
 * and astra_uart_receive() functions to interact with the protocol layer
 * without needing to worry about the underlying UART details or task management.
 */

#include "astra_codec.h" // IWYU pragma: keep

#include "FreeRTOS.h" // IWYU pragma: keep
#include "portmacro.h"

/**
 * @brief Initializes the ASTRA UART protocol layer.
 *
 * Creates the TX and RX FreeRTOS queues and spawns the uart_tx_task and
 * uart_rx_task background tasks.  Must be called once after uart2Init().
 *
 * @return true if all resources were created successfully, false otherwise.
 */
bool astra_uart_init(uint32_t baudrate);

/**
 * @brief Enqueues a packet for transmission over UART.
 *
 * Thread-safe.  The packet is copied into the TX queue and sent
 * asynchronously by the uart_tx_task.
 *
 * @param packet      Packet to send.
 * @param timeout_ms  Maximum time to wait for queue space (ms).
 *                    Pass 0 to return immediately if the queue is full.
 *
 * @return true if the packet was enqueued, false if the queue was full within
 *         the timeout or the protocol layer has not been initialized.
 */
BaseType_t astra_uart_send(const astra_uart_packet_t *packet, TickType_t timeout);

/**
 * @brief Receives the next packet from the RX queue.
 *
 * Blocks until a packet is available or the timeout elapses.
 *
 * @param out_packet  Populated with the received packet on success.
 * @param timeout_ms  Maximum time to wait for a packet (ms).
 *                    Pass 0 to return immediately if the queue is empty.
 *
 * @return true if a packet was retrieved, false if the queue was empty within
 *         the timeout or the protocol layer has not been initialized.
 */
BaseType_t astra_uart_receive(astra_uart_packet_t *out_packet, TickType_t timeout);
