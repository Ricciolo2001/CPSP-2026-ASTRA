#include "uart_framing.h"

#include <assert.h>
#include <string.h>

#include "lib/cobs.h"
#include "lib/crc16.h"

#define DEBUG_MODULE "UART_FRAMING"
#include "astra_debug.h"

/**
 * Frame layout (before the 0x00 delimiter):
 *
 *   COBS( payload[0..N-1] | CRC16_MSB | CRC16_LSB )  |  0x00
 *
 * The CRC16 is computed over the raw payload only (not over the CRC bytes
 * themselves) and is stored big-endian (MSB first).
 */

/* Byte budgets added on top of the raw payload length. */
#define CRC_SIZE 2U       /* two CRC bytes appended before COBS encoding   */
#define COBS_OVERHEAD 1U  /* COBS always prepends one code byte             */
#define DELIMITER_SIZE 1U /* trailing 0x00 frame delimiter                  */
#define FRAME_OVERHEAD (CRC_SIZE + COBS_OVERHEAD + DELIMITER_SIZE)

/* Minimum number of decoded bytes required to contain at least one CRC pair. */
#define MIN_DECODED_LEN CRC_SIZE

/* Bit shift and mask used when packing/unpacking the big-endian CRC16 bytes. */
#define CRC_BYTE_SHIFT 8U /* shift MSB into/out of the high byte position */
#define BYTE_MASK 0xFFU   /* isolate the low byte of a wider integer       */

size_t uart_frame_encode(const uint8_t *payload, size_t payload_len,
                         uint8_t *out_buf, size_t out_max) {
    if (payload == NULL || out_buf == NULL) {
        return 0;
    }

    if (payload_len + FRAME_OVERHEAD > out_max) {
        return 0; /* output buffer too small */
    }

    /* --- Step 1: build temp buffer = payload || CRC16 --- */
    uint8_t temp[payload_len + CRC_SIZE];
    memcpy(temp, payload, payload_len);

    uint32_t crc = crc16_compute(payload, payload_len);
    temp[payload_len] = (uint8_t)(crc >> CRC_BYTE_SHIFT); /* MSB */
    temp[payload_len + 1] = (uint8_t)(crc & BYTE_MASK);   /* LSB */

    /* --- Step 2: COBS encode into out_buf --- */
    size_t encoded_len = 0;
    cobs_status_t status =
        cobs_encode(temp, sizeof(temp), out_buf, out_max, &encoded_len);

    if (status != COBS_RET_OK) {
        return 0;
    }

    /* --- Step 3: append 0x00 frame delimiter --- */
    out_buf[encoded_len] = 0x00U;

    return encoded_len + DELIMITER_SIZE;
}

bool uart_frame_decode(const uint8_t *frame, size_t frame_len,
                       uint8_t *out_payload, size_t out_max, size_t *out_len) {
    assert(frame != NULL && "frame pointer is NULL");
    assert(out_payload != NULL && "out_payload pointer is NULL");
    assert(out_len != NULL && "out_len pointer is NULL");

    /* Need at least the COBS code byte + two CRC bytes + delimiter. */
    if (frame_len < (COBS_OVERHEAD + CRC_SIZE + DELIMITER_SIZE)) {
        DEBUG_PRINT("Frame too short: %d bytes (minimum is %d)\n", frame_len,
                    COBS_OVERHEAD + CRC_SIZE + DELIMITER_SIZE);
        return false;
    }

    /* --- Step 1: COBS decode (exclude the trailing 0x00 delimiter) --- */
    size_t cobs_input_len = frame_len - DELIMITER_SIZE;

    /* Decoded output holds the payload plus the two CRC bytes. */
    uint8_t decoded[out_max + CRC_SIZE];
    size_t decoded_len = 0;

    cobs_status_t status = cobs_decode(frame, cobs_input_len, decoded,
                                       sizeof(decoded), &decoded_len);
    if (status != COBS_RET_OK) {
        DEBUG_PRINT("COBS decode failed: status=%d\n", (int)status);
        return false;
    }
    if (decoded_len < MIN_DECODED_LEN) {
        DEBUG_PRINT("Decoded output too short: %d bytes (minimum is %d)\n",
                    decoded_len, MIN_DECODED_LEN);
        return false;
    }

    /* --- Step 2: split decoded output into payload and CRC --- */
    size_t payload_len = decoded_len - CRC_SIZE;

    if (payload_len > out_max) {
        DEBUG_PRINT(
            "Payload too large for output buffer: %d bytes (max is %d)\n",
            payload_len, out_max);
        return false; /* caller's buffer too small for the payload */
    }

    uint16_t received_crc =
        (uint16_t)(((uint16_t)decoded[payload_len] << CRC_BYTE_SHIFT) |
                   (uint16_t)decoded[payload_len + 1]);

    /* --- Step 3: verify CRC over the raw payload bytes --- */
    uint16_t calculated_crc = crc16_compute(decoded, payload_len);

    if (received_crc != calculated_crc) {
        DEBUG_PRINT("CRC check failed: received 0x%04x, calculated 0x%04x\n",
                    received_crc, calculated_crc);
        return false;
    }

    /* --- Step 4: copy verified payload to caller's buffer --- */
    memcpy(out_payload, decoded, payload_len);
    *out_len = payload_len;

    return true;
}
