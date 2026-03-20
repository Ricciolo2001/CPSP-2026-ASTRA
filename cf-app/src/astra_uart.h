#pragma once

/**
 * astra_uart.h - ASTRA application protocol over UART
 *
 * Defines the application-level message types exchanged between the Crazyflie
 * and the ESP32 BLE bridge over the UART2 link.
 *
 * Responsibilities of this module:
 *   - Packet-type enumeration and payload struct definitions.
 *   - Serialization / deserialization of astra_uart_packet_t to/from raw bytes.
 *   - Lifecycle management: task creation and queue initialization.
 *   - Public send / receive API backed by FreeRTOS queues.
 *
 * Wire framing (COBS + CRC16) is handled separately by uart_framing.h/c and
 * is NOT part of this module's concern.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* -------------------------------------------------------------------------
 * BLE address type
 * ---------------------------------------------------------------------- */

#define ASTRA_BLE_ADDR_LEN 6

typedef uint8_t astra_dev_addr_t[ASTRA_BLE_ADDR_LEN];

/* -------------------------------------------------------------------------
 * Packet types
 * ---------------------------------------------------------------------- */

typedef enum {
  ASTRA_UART_BIND_REQUEST   = 0x01,
  ASTRA_UART_BIND_RESPONSE  = 0x02,
  ASTRA_UART_UNBIND_REQUEST = 0x03,
  ASTRA_UART_UNBIND_RESPONSE = 0x04,
  ASTRA_UART_RSSI_VALUE     = 0x05,
} astra_uart_packet_type_t;

/* -------------------------------------------------------------------------
 * Payload structs
 * ---------------------------------------------------------------------- */

typedef struct __attribute__((packed)) {
  astra_dev_addr_t device_addr;
} astra_uart_bind_request_t;

typedef struct __attribute__((packed)) {
  bool success;
} astra_uart_bind_response_t;

typedef struct __attribute__((packed)) {
  astra_dev_addr_t device_addr;
  int8_t rssi;
} astra_uart_rssi_value_t;

/* -------------------------------------------------------------------------
 * Top-level packet (type tag + union of payloads)
 * ---------------------------------------------------------------------- */

typedef struct __attribute__((packed)) {
  uint8_t type; /**< One of astra_uart_packet_type_t */
  union {
    astra_uart_bind_request_t  bind_request;
    astra_uart_bind_response_t bind_response;
    astra_uart_rssi_value_t    rssi_value;
  } payload;
} astra_uart_packet_t;

/* -------------------------------------------------------------------------
 * Serialization / deserialization
 * ---------------------------------------------------------------------- */

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

/* -------------------------------------------------------------------------
 * Lifecycle
 * ---------------------------------------------------------------------- */

/**
 * @brief Initializes the ASTRA UART protocol layer.
 *
 * Creates the TX and RX FreeRTOS queues and spawns the uart_tx_task and
 * uart_rx_task background tasks.  Must be called once after uart2Init().
 *
 * @return true if all resources were created successfully, false otherwise.
 */
bool astra_uart_init(void);

/* -------------------------------------------------------------------------
 * Public send / receive API
 * ---------------------------------------------------------------------- */

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
bool astra_uart_send(const astra_uart_packet_t *packet, uint32_t timeout_ms);

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
bool astra_uart_receive(astra_uart_packet_t *out_packet, uint32_t timeout_ms);