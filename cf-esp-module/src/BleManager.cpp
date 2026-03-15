#include "BleManager.h"

#include <cmath>
#include <mutex>

#include "freertos/semaphore.hpp"

void RssiFilter::update(float newSample) {
    if (isFirstSample_) {
        currentAverage_ = newSample;
        isFirstSample_ = false;
    } else {
        currentAverage_ =
            (alpha_ * newSample) + ((1.0f - alpha_) * currentAverage_);
    }
}

// ! Da calibrare per il singolo sensore, guardare una guida su come fare (la
// calibrazione andrebbe fatta ad un metro di distnaza) ! Ovviamente le board
// che usiamo sono merdose, no shielding e no rf matching (catena di induttori e
// condensatori) quindi non avremo risultati solidi... ! Nell'AI deck invece c'è
// un RF matching fatto bene, e un bellissimo shield per le interferenze...

BleManager &BleManager::instance() {
    static BleManager inst;
    return inst;
}

BleManager::~BleManager() { stopBackgroundScan(); }

void BleManager::applyScanParams(bool active) {
    NimBLEScan *pScan = NimBLEDevice::getScan();
    if (active) {
        pScan->setActiveScan(true);
        pScan->setInterval(100); // 99% duty cycle
        pScan->setWindow(99);
    } else {
        pScan->setActiveScan(false);
        pScan->setInterval(200); // default 50/200
        pScan->setWindow(50);
    }
}

void BleManager::init() {
    NimBLEDevice::init("");
    NimBLEScan *pScan = NimBLEDevice::getScan();
    pScan->setAdvertisedDeviceCallbacks(this, false);
    pScan->setDuplicateFilter(false);
    applyScanParams(false);
}

void BleManager::startBackgroundScan() {
    _bgScanActive.store(true, std::memory_order_relaxed);
    applyScanParams(false);
    // Non-blocking: returns immediately after posting to NimBLE's event queue.
    // The callback is invoked on Core 0 (NimBLE host task) when the scan ends.
    NimBLEDevice::getScan()->start(1, &BleManager::onBgScanComplete, false);
}

void BleManager::stopBackgroundScan() {
    if (!_bgScanActive.exchange(false, std::memory_order_relaxed))
        return;
    NimBLEDevice::getScan()->stop();
    _bgScanStopped.take(pdMS_TO_TICKS(2000));
}

// Called on Core 0 by NimBLE when a 1-second background scan cycle ends.
void BleManager::onBgScanComplete(NimBLEScanResults /*results*/) {
    NimBLEDevice::getScan()->clearResults();
    if (instance()._bgScanActive.load(std::memory_order_relaxed)) {
        NimBLEDevice::getScan()->start(1, &BleManager::onBgScanComplete, false);
    } else {
        instance()._bgScanStopped.give();
    }
}

void BleManager::onResult(NimBLEAdvertisedDevice *advertisedDevice) {
    std::lock_guard lock(_mutex);

    auto addr = advertisedDevice->getAddress();
    auto addrStr = addr.toString();

    if (_targetAddr != "" && addrStr == _targetAddr) {
        _targetRssiFilter.update(advertisedDevice->getRSSI());
        _targetLastSeenTime = millis();
    }
}

std::vector<BleDevice> BleManager::scanDevices(uint32_t duration_seconds,
                                               bool active) {
    // Stop background scan and wait for the current cycle to end (≤1 s).
    if (_bgScanActive.exchange(false, std::memory_order_relaxed)) {
        NimBLEDevice::getScan()->stop();
        _bgScanStopped.take(pdMS_TO_TICKS(2000));
    }

    // Start the manual scan — non-blocking, results arrive in the callback.
    NimBLEDevice::getScan()->clearResults();
    applyScanParams(active);
    NimBLEDevice::getScan()->start(duration_seconds,
                                   &BleManager::onManualScanComplete, false);

    _manualScanDone.take(pdMS_TO_TICKS((duration_seconds + 2) * 1000));
    return _manualScanResults;
}

// Called on Core 0 by NimBLE when the manual scan finishes.
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
    NimBLEDevice::getScan()->clearResults();

    instance()._manualScanResults = std::move(list);
    instance()._manualScanDone.give();

    // Resume background scanning — safe here because we're on Core 0.
    instance().startBackgroundScan();
}

bool BleManager::setTargetDevice(std::string name) {
    std::lock_guard lock(_mutex);
    _targetAddr = name;
    _targetRssiFilter = RssiFilter();
    _targetLastSeenTime = 0;
    return true;
}

float BleManager::getTargetRssi() {
    std::lock_guard lock(_mutex);
    if (_targetAddr == "") {
        return -1.0f;
    }
    if (millis() - _targetLastSeenTime > _timeoutMs) {
        return -1.0f;
    }
    return _targetRssiFilter.get();
}
