#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* -------------------------------------------------------------------------
 * BLE address type
 * ---------------------------------------------------------------------- */

#define ASTRA_BLE_ADDR_LEN 6

typedef struct __attribute__((packed)) {
    uint8_t bytes[ASTRA_BLE_ADDR_LEN];
} astra_dev_addr_t;

/* -------------------------------------------------------------------------
 * Packet types
 * ---------------------------------------------------------------------- */

typedef enum {
    ASTRA_UART_BIND_REQUEST = 0x01,
    ASTRA_UART_BIND_RESPONSE = 0x02,
    ASTRA_UART_UNBIND_REQUEST = 0x03,
    ASTRA_UART_UNBIND_RESPONSE = 0x04,
    ASTRA_UART_RSSI_VALUE = 0x05,
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
        astra_uart_bind_request_t bind_request;
        astra_uart_bind_response_t bind_response;
        astra_uart_rssi_value_t rssi_value;
    } payload;
} astra_uart_packet_t;
