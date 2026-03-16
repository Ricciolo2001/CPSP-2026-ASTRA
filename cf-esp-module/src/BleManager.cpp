#include "BleManager.h"

#include <cmath>
#include <mutex>

#include "freertos/semaphore.hpp"

// ! Da calibrare per il singolo sensore, guardare una guida su come fare (la
// calibrazione andrebbe fatta ad un metro di distnaza) ! Ovviamente le board
// che usiamo sono merdose, no shielding e no rf matching (catena di induttori e
// condensatori) quindi non avremo risultati solidi... ! Nell'AI deck invece c'è
// un RF matching fatto bene, e un bellissimo shield per le interferenze...

BleManager &BleManager::instance() {
    static BleManager inst;
    return inst;
}

BleManager::BleManager() : _targetRssiFilter{0} {
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
    _bgScanActive.store(true, std::memory_order_relaxed);
    applyScanParams(ScanMode::Background);
    NimBLEDevice::getScan()->start(1, &BleManager::onBgScanComplete, false);
}

void BleManager::stopBackgroundScan() {
    if (!_bgScanActive.exchange(false, std::memory_order_relaxed)) {
        return; // Already stopped, nothing to do
    }
    NimBLEDevice::getScan()->stop();
    /// Wait for onBgScanComplete to signal that the background scan has fully
    /// stopped before returning.
    _bgScanStopped.take(pdMS_TO_TICKS(_bgScanPeriodMs + 1000));
}

void BleManager::onResult(NimBLEAdvertisedDevice *advertisedDevice) {
    std::lock_guard lock(_targetMutex);

    auto addr = advertisedDevice->getAddress();
    auto addrStr = addr.toString();

    if (!_targetAddr.empty() && addrStr == _targetAddr) {
        _targetRssiFilter.update(advertisedDevice->getRSSI());
        _targetLastSeenTime = millis();
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

    if (!_manualScanDone.take(pdMS_TO_TICKS((duration_seconds + 2) * 1000))) {
        // Timeout: manual scan didn't finish in expected time
        return {};
    }
    return std::move(_manualScanResults);
}

void BleManager::onBgScanComplete(NimBLEScanResults) {
    NimBLEDevice::getScan()->clearResults();
    // If we're still supposed to be in background scan mode, restart
    // immediately. Otherwise, signal that the background scan has fully
    // stopped.
    if (instance()._bgScanActive.load(std::memory_order_relaxed)) {
        NimBLEDevice::getScan()->start(1, &BleManager::onBgScanComplete, false);
    } else {
        instance()._bgScanStopped.give();
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

    instance()._manualScanResults = std::move(list);
    instance()._manualScanDone.give();

    // Resume background scanning
    NimBLEDevice::getScan()->clearResults();
    instance().startBackgroundScan();
}

void BleManager::setTargetDevice(std::string name) {
    std::lock_guard lock(_targetMutex);
    _targetAddr = name;
    _targetRssiFilter = EwmaFilter<float>{};
    _targetLastSeenTime = 0;
}

float BleManager::getTargetRssi() {
    std::lock_guard lock(_targetMutex);
    if (_targetAddr.empty()) {
        return -1.0f;
    }
    if (millis() - _targetLastSeenTime > _timeoutMs) {
        return -1.0f;
    }
    return _targetRssiFilter.get();
}
