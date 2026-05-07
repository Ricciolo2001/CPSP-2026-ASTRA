// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 Eyad Issa
// SPDX-FileCopyrightText: 2026 Alessandro Armandi

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "AstraUart.hpp"
#include "BleManager.hpp"

/* -------------------------------------------------------------------------
 * UART hardware configuration
 * ---------------------------------------------------------------------- */

static const UartPort::Config kUartConfig = {
    UART_NUM_1,
    2048, // TX buffer size
    2048, // RX buffer size
    {
        115200,                   // Baudrate
        UART_DATA_8_BITS,         // Data bits
        UART_PARITY_DISABLE,      // Parity
        UART_STOP_BITS_1,         // Stop bits
        UART_HW_FLOWCTRL_DISABLE, // Flow control
    },
    GPIO_NUM_5, // TX pin
    GPIO_NUM_6, // RX pin
};

/* -------------------------------------------------------------------------
 * Helpers
 * ---------------------------------------------------------------------- */

/// Convert a raw 6-byte BLE address (LSB first) to "AA:BB:CC:DD:EE:FF".
static std::string addrBytesToString(const astra_dev_addr_t addr) {
    char buf[18];
    snprintf(buf, sizeof(buf), "%02X:%02X:%02X:%02X:%02X:%02X", addr.bytes[5],
             addr.bytes[4], addr.bytes[3], addr.bytes[2], addr.bytes[1],
             addr.bytes[0]);
    return buf;
}

/* -------------------------------------------------------------------------
 * Command dispatch
 * ---------------------------------------------------------------------- */

static void handlePacket(AstraUart &uart, BleManager &ble,
                         const astra_uart_packet_t &pkt) {

    switch ((astra_uart_packet_type_t)pkt.type) {

    case ASTRA_UART_BIND_REQUEST: {
        astra_dev_addr_t addr = pkt.payload.bind_request.device_addr;
        Serial.printf("CMD BIND → %s\n", addrBytesToString(addr).c_str());
        ble.setTargetDevice(addr);

        astra_uart_packet_t resp{};
        resp.type = ASTRA_UART_BIND_RESPONSE;
        resp.payload.bind_response.success = true;
        uart.send(resp);
        break;
    }

    case ASTRA_UART_UNBIND_REQUEST: {
        Serial.println("CMD UNBIND");
        ble.clearTargetDevice();

        astra_uart_packet_t resp{};
        resp.type = ASTRA_UART_UNBIND_RESPONSE;
        uart.send(resp);
        break;
    }

    default:
        Serial.printf("Unknown packet type: 0x%02x\n", (unsigned)pkt.type);
        break;
    }
}

/* -------------------------------------------------------------------------
 * Dispatch task
 * ---------------------------------------------------------------------- */

static void dispatch_task(void *) {
    BleManager &ble = BleManager::instance();
    AstraUart uart{kUartConfig};

    while (true) {
        // Handle one incoming command per iteration (10 ms timeout keeps the
        // loop responsive without busy-waiting).
        astra_uart_packet_t pkt{};
        if (uart.receive(pkt, pdMS_TO_TICKS(10)) == pdTRUE) {
            Serial.println("Received command packet over UART");
            handlePacket(uart, ble, pkt);
        }

        // Drain all RSSI observations queued by the BLE scan callback and
        // forward each one as an RSSI packet over UART.
        astra_uart_rssi_value_t rssi{};
        while (ble.receiveRssi(&rssi, 0) == pdTRUE) {
            Serial.println("New RSSI observation: " + String(rssi.rssi) +
                           " from " +
                           addrBytesToString(rssi.device_addr).c_str());
            astra_uart_packet_t out{};
            out.type = ASTRA_UART_RSSI_VALUE;
            out.payload.rssi_value = rssi;
            uart.send(out);
        }
    }
}

/* -------------------------------------------------------------------------
 * Arduino entry points
 * ---------------------------------------------------------------------- */

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("Serial monitor setup complete.");

    BleManager &ble = BleManager::instance();
    ble.startBackgroundScan();
    Serial.println("BLE Manager initialized, background scan running.");

    pinMode(BUILTIN_LED, OUTPUT);
    digitalWrite(BUILTIN_LED, HIGH);

    xTaskCreate(dispatch_task, "dispatch_task", 4096, nullptr, 10, nullptr);

    vTaskDelete(NULL);
}

void loop() {
    // Never called — the Arduino loop task is deleted in setup().
}
