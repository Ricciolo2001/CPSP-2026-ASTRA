// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 Eyad Issa

#include "astra_codec.h"

#include <assert.h>
#include <stddef.h>
#include <string.h>

bool astra_uart_serialize(const astra_uart_packet_t *packet, uint8_t *out_buf, size_t out_max, size_t *out_len) {
  assert(packet != NULL && "packet must not be NULL");
  assert(out_buf != NULL && "out_buf must not be NULL");
  assert(out_len != NULL && "out_len must not be NULL");

  // Resolve the payload size for this packet type up-front so that we only
  // need a single bounds check before writing anything to out_buf.
  size_t payload_size = 0;
  const void *payload_ptr = NULL;

  switch (packet->type) {
  case ASTRA_UART_BIND_REQUEST:
    payload_ptr = &packet->payload.bind_request;
    payload_size = sizeof(packet->payload.bind_request);
    break;
  case ASTRA_UART_BIND_RESPONSE:
    payload_ptr = &packet->payload.bind_response;
    payload_size = sizeof(packet->payload.bind_response);
    break;
  case ASTRA_UART_RSSI_VALUE:
    payload_ptr = &packet->payload.rssi_value;
    payload_size = sizeof(packet->payload.rssi_value);
    break;
  case ASTRA_UART_UNBIND_REQUEST:
  case ASTRA_UART_UNBIND_RESPONSE:
    /* No payload for these packet types */
    payload_ptr = NULL;
    payload_size = 0;
    break;
  default:
    return false; /* unknown / unimplemented packet type */
  }

  size_t total = 1U /* type tag */ + payload_size;
  if (total > out_max) {
    return false;
  }

  out_buf[0] = packet->type; // write the type tag
  if (payload_size > 0) {
    memcpy(&out_buf[1], payload_ptr, payload_size); // write the payload
  }

  *out_len = total;
  return true;
}

bool astra_uart_deserialize(const uint8_t *data, size_t data_len, astra_uart_packet_t *out_packet) {
  assert(data != NULL && "data must not be NULL");
  assert(out_packet != NULL && "out_packet must not be NULL");

  if (data_len < 1U) {
    return false; /* need at least the type tag */
  }

  out_packet->type = data[0];

  const uint8_t *payload_data = data + 1;
  size_t payload_len = data_len - 1U;

  void *expected_payload_ptr = NULL;
  size_t expected_payload_size = 0;

  switch ((astra_uart_packet_type_t)out_packet->type) {
  case ASTRA_UART_BIND_REQUEST:
    expected_payload_ptr = &out_packet->payload.bind_request;
    expected_payload_size = sizeof(out_packet->payload.bind_request);
    break;
  case ASTRA_UART_BIND_RESPONSE:
    expected_payload_ptr = &out_packet->payload.bind_response;
    expected_payload_size = sizeof(out_packet->payload.bind_response);
    break;
  case ASTRA_UART_RSSI_VALUE:
    expected_payload_ptr = &out_packet->payload.rssi_value;
    expected_payload_size = sizeof(out_packet->payload.rssi_value);
    break;
  case ASTRA_UART_UNBIND_REQUEST:
  case ASTRA_UART_UNBIND_RESPONSE:
    /* No payload for these packet types */
    expected_payload_ptr = NULL;
    expected_payload_size = 0;
    break;
  default:
    return false; /* unknown / unimplemented packet type */
  }

  if (payload_len != expected_payload_size) {
    return false; /* payload length mismatch */
  }
  if (expected_payload_size > 0) {
    memcpy(expected_payload_ptr, payload_data, expected_payload_size);
  }

  return true;
}

int astra_dev_addr_cmp(const astra_dev_addr_t *addr1, const astra_dev_addr_t *addr2) {
  return memcmp(addr1->bytes, addr2->bytes, ASTRA_BLE_ADDR_LEN);
}
