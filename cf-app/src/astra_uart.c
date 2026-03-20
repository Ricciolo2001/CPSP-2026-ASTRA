#include "astra_uart.h"

#include <assert.h>
#include <string.h>

#include "portmacro.h"
#include "uart_framing.h"

#include "FreeRTOS.h" // IWYU pragma: keep
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
static bool s_initialized = false;

/* -------------------------------------------------------------------------
 * Serialization / deserialization
 * ---------------------------------------------------------------------- */

int astra_dev_addr_equal(const astra_dev_addr_t *addr1, const astra_dev_addr_t *addr2) {
  return memcmp(addr1->bytes, addr2->bytes, ASTRA_BLE_ADDR_LEN);
}

bool astra_uart_serialize(const astra_uart_packet_t *packet, uint8_t *out_buf, size_t out_max, size_t *out_len) {
  if (packet == NULL || out_buf == NULL || out_len == NULL) {
    return false;
  }

  /* Resolve the payload size for this packet type up-front so that we only
   * need a single bounds check before writing anything to out_buf.          */
  size_t payload_size;
  switch ((astra_uart_packet_type_t)packet->type) {
  case ASTRA_UART_BIND_REQUEST:
    payload_size = sizeof(packet->payload.bind_request);
    break;
  case ASTRA_UART_BIND_RESPONSE:
    payload_size = sizeof(packet->payload.bind_response);
    break;
  case ASTRA_UART_RSSI_VALUE:
    payload_size = sizeof(packet->payload.rssi_value);
    break;
  default:
    return false; /* unknown / unimplemented packet type */
  }

  size_t total = 1U /* type tag */ + payload_size;
  if (total > out_max) {
    return false;
  }

  out_buf[0] = packet->type;

  switch ((astra_uart_packet_type_t)packet->type) {
  case ASTRA_UART_BIND_REQUEST:
    memcpy(&out_buf[1], &packet->payload.bind_request, payload_size);
    break;
  case ASTRA_UART_BIND_RESPONSE:
    memcpy(&out_buf[1], &packet->payload.bind_response, payload_size);
    break;
  case ASTRA_UART_RSSI_VALUE:
    memcpy(&out_buf[1], &packet->payload.rssi_value, payload_size);
    break;
  default:
    return false;
  }

  *out_len = total;
  return true;
}

bool astra_uart_deserialize(const uint8_t *data, size_t data_len, astra_uart_packet_t *out_packet) {
  if (data == NULL || out_packet == NULL) {
    return false;
  }

  if (data_len < 1U) {
    return false; /* need at least the type tag */
  }

  out_packet->type = data[0];

  const uint8_t *payload_data = data + 1;
  size_t payload_len = data_len - 1U;

  switch ((astra_uart_packet_type_t)out_packet->type) {
  case ASTRA_UART_BIND_REQUEST:
    if (payload_len != sizeof(out_packet->payload.bind_request)) {
      return false;
    }
    memcpy(&out_packet->payload.bind_request, payload_data, payload_len);
    break;
  case ASTRA_UART_BIND_RESPONSE:
    if (payload_len != sizeof(out_packet->payload.bind_response)) {
      return false;
    }
    memcpy(&out_packet->payload.bind_response, payload_data, payload_len);
    break;
  case ASTRA_UART_RSSI_VALUE:
    if (payload_len != sizeof(out_packet->payload.rssi_value)) {
      return false;
    }
    memcpy(&out_packet->payload.rssi_value, payload_data, payload_len);
    break;
  default:
    return false; /* unknown / unimplemented packet type */
  }

  return true;
}

/* -------------------------------------------------------------------------
 * Internal tasks
 * ---------------------------------------------------------------------- */

static void uart_tx_task(void *params) {
  (void)params;

  uint8_t raw_buf[RAW_BUF_SIZE];
  uint8_t frame_buf[FRAME_BUF_SIZE];

  while (1) {
    astra_uart_packet_t packet;
    if (xQueueReceive(s_tx_queue, &packet, portMAX_DELAY) != pdTRUE) {
      continue;
    }

    size_t raw_len = 0;
    if (!astra_uart_serialize(&packet, raw_buf, sizeof(raw_buf), &raw_len)) {
      DEBUG_PRINT("TX: serialize failed (type=0x%02x)\n", (unsigned)packet.type);
      continue;
    }

    size_t frame_len = uart_frame_encode(raw_buf, raw_len, frame_buf, sizeof(frame_buf));
    if (frame_len == 0U) {
      DEBUG_PRINT("TX: frame encode failed\n");
      continue;
    }

    uart2SendData((uint32_t)frame_len, frame_buf);
  }
}

static void uart_rx_task(void *params) {
  (void)params;

  uint8_t frame_buf[FRAME_BUF_SIZE];
  uint8_t raw_buf[RAW_BUF_SIZE];

  while (1) {
    int received = uart2GetData(sizeof(frame_buf), frame_buf);
    if (received <= 0) {
      continue;
    }
    size_t frame_len = (size_t)received;

    size_t raw_len = 0;
    if (!uart_frame_decode(frame_buf, frame_len, raw_buf, sizeof(raw_buf), &raw_len)) {
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
    return false;
  }

  BaseType_t tx_ok = xTaskCreate(uart_tx_task, "astra_uart_tx", TASK_STACK_WORDS, NULL, TASK_PRIORITY, NULL);
  BaseType_t rx_ok = xTaskCreate(uart_rx_task, "astra_uart_rx", TASK_STACK_WORDS, NULL, TASK_PRIORITY, NULL);

  if (tx_ok != pdPASS || rx_ok != pdPASS) {
    DEBUG_PRINT("Failed to create UART tasks\n");
    return false;
  }

  s_initialized = true;
  return true;
}

/* -------------------------------------------------------------------------
 * Public send / receive API
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
