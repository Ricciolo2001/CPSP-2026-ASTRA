// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 Eyad Issa
// SPDX-FileCopyrightText: 2026 Alessandro Armandi

#include "BleManager.hpp"

#include <cmath>
#include <cstring>
#include <mutex>

#include <freertos/Semaphore.hpp>
#include <freertos/queue.h>

bool operator==(const astra_dev_addr_t &lhs, const astra_dev_addr_t &rhs) {
    return std::memcmp(lhs.bytes, rhs.bytes, ASTRA_BLE_ADDR_LEN) == 0;
}

// It is good practice to also provide the inequality operator
bool operator!=(const astra_dev_addr_t &lhs, const astra_dev_addr_t &rhs) {
    return !(lhs == rhs);
}

BleManager &BleManager::instance() {
    static BleManager inst;
    return inst;
}

BleManager::BleManager() {
    NimBLEDevice::init("");
    NimBLEScan *pScan = NimBLEDevice::getScan();

    // Set this class as the nimble callback handler
    pScan->setAdvertisedDeviceCallbacks(this, true);
}

BleManager::~BleManager() { stopBackgroundScan(); }

void BleManager::applyScanParams(ScanMode mode) {
    NimBLEScan *pScan = NimBLEDevice::getScan();
    if (mode == ScanMode::Discovery) {
        pScan->setActiveScan(true);
        pScan->setInterval(100);
        pScan->setWindow(99);
    } else {
        pScan->setActiveScan(false);
        pScan->setInterval(200);
        pScan->setWindow(50);
    }
}

void BleManager::startBackgroundScan() {
    bgScanActive_.store(true, std::memory_order_relaxed);
    applyScanParams(ScanMode::Background);
    NimBLEDevice::getScan()->start(1, &BleManager::onBgScanComplete, false);
}

void BleManager::stopBackgroundScan() {
    if (!bgScanActive_.exchange(false, std::memory_order_relaxed)) {
        return; // Already stopped, nothing to do
    }
    NimBLEDevice::getScan()->stop();
    /// Wait for onBgScanComplete to signal that the background scan has fully
    /// stopped before returning.
    bgScanStopped_.take(pdMS_TO_TICKS(bgScanPeriodMs_ + 1000));
}

namespace {
astra_dev_addr_t addrBytesToAstraDevAddr(const uint8_t *bytes) {
    astra_dev_addr_t addr{};
    memcpy(addr.bytes, bytes, ASTRA_BLE_ADDR_LEN);
    return addr;
}
} // namespace

void BleManager::onResult(NimBLEAdvertisedDevice *advertisedDevice) {
    std::lock_guard lock(targetMutex_);

    auto nimbleAddr = advertisedDevice->getAddress();

    // NimBLE: little-endian (LSB first)
    const uint8_t *val = nimbleAddr.getNative();

    // Convert to astra_dev_addr_t
    astra_dev_addr_t advertDevAddr = addrBytesToAstraDevAddr(val);

    if (advertDevAddr == targetAddr_) {
        int8_t rssi = advertisedDevice->getRSSI();
        targetRssiLast_ = rssi;
        targetLastSeenTime_ = millis();

        Serial.printf("Updated target device RSSI: %d\n", rssi);

        // Push raw observation to the outgoing queue (non-blocking; drop if
        // full).
        astra_uart_rssi_value_t item = {
            .device_addr = addrBytesToAstraDevAddr(val),
            .rssi = rssi,
        };
        rssiQueue_.send(item, 0);
    }
}

std::vector<BleDevice> BleManager::scanDevices(uint32_t duration_seconds) {
    // Stop background scan and wait for the current cycle to end (≤1 s).
    stopBackgroundScan();

    // Start the manual scan — non-blocking, results arrive in the callback.
    NimBLEDevice::getScan()->clearResults();
    applyScanParams(ScanMode::Discovery);
    NimBLEDevice::getScan()->start(duration_seconds,
                                   &BleManager::onManualScanComplete, false);

    if (!manualScanDone_.take(pdMS_TO_TICKS((duration_seconds + 2) * 1000))) {
        // Timeout: manual scan didn't finish in expected time
        return {};
    }
    return std::move(manualScanResults_);
}

void BleManager::onBgScanComplete(NimBLEScanResults) {
    NimBLEDevice::getScan()->clearResults();
    // If we're still supposed to be in background scan mode, restart
    // immediately. Otherwise, signal that the background scan has fully
    // stopped.
    if (instance().bgScanActive_.load(std::memory_order_relaxed)) {
        NimBLEDevice::getScan()->start(1, &BleManager::onBgScanComplete, false);
    } else {
        instance().bgScanStopped_.give();
    }
}

void BleManager::onManualScanComplete(NimBLEScanResults results) {
    std::vector<BleDevice> list;
    list.reserve(results.getCount());
    for (auto *device : results) {
        // 1. Get the Service UUID (if it exists)
        std::string serviceUUIDStr = "";
        if (device->haveServiceUUID()) {
            serviceUUIDStr = device->getServiceUUID().toString();
        }

        // 2. Get Service Data
        // Note: Some devices have multiple service data entries.
        // This gets the data for the FIRST UUID found.
        std::string servDataHex = "";
        if (device->getServiceDataCount() > 0) {
            // Get the UUID associated with the first piece of service data
            NimBLEUUID uuid = device->getServiceDataUUID(0);
            servDataHex = device->getServiceData(uuid);
            // Note: NimBLE returns this as a string of raw bytes
        }

        list.emplace_back(device->getName(), device->getAddress().toString(),
                          device->getRSSI(), serviceUUIDStr, servDataHex);
    }

    instance().manualScanResults_ = std::move(list);
    instance().manualScanDone_.give();

    // Resume background scanning
    NimBLEDevice::getScan()->clearResults();
    instance().startBackgroundScan();
}

void BleManager::setTargetDevice(astra_dev_addr_t addr) {
    std::lock_guard lock(targetMutex_);
    targetAddr_ = addr;
    targetRssiLast_ = 0;
    targetLastSeenTime_ = 0;
    rssiQueue_.reset();
}

void BleManager::clearTargetDevice() {
    std::lock_guard lock(targetMutex_);
    targetAddr_ = {};
    targetRssiLast_ = 0;
    targetLastSeenTime_ = 0;
    rssiQueue_.reset();
}

BaseType_t BleManager::receiveRssi(astra_uart_rssi_value_t *out,
                                   TickType_t timeout) {
    return rssiQueue_.receive(*out, timeout);
}

float BleManager::getTargetRssi() {
    std::lock_guard lock(targetMutex_);
    if (targetAddr_ == astra_dev_addr_t{}) {
        return -1.0f;
    }
    if (millis() - targetLastSeenTime_ > timeoutMs_) {
        return -1.0f;
    }
    return targetRssiLast_;
}
