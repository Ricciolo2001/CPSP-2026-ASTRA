#include "BLE_manager.h"
#include <Arduino.h>

const int MEASURED_POWER = -60;
const float N_FACTOR = 2.5;

BleManager::BleManager() : _targetName(""), _lastTargetDistance(-1.0) {}

void BleManager::init() {
    NimBLEDevice::init("");
    NimBLEScan* pScan = NimBLEDevice::getScan();
    pScan->setAdvertisedDeviceCallbacks(this, false);
    pScan->setActiveScan(true);
    pScan->setInterval(45); // Più veloce per non perdere pacchetti
    pScan->setWindow(15);
}

float BleManager::calculateDistance(int rssi) {
    if (rssi == 0) return -1.0;
    return pow(10, (float)(MEASURED_POWER - rssi) / (10 * N_FACTOR));
}

void BleManager::onResult(NimBLEAdvertisedDevice* advertisedDevice) {
    // Se è il dispositivo che stiamo monitorando, aggiorniamo la distanza IMMEDIATAMENTE
    if (_targetName != "" && advertisedDevice->getName() == _targetName) {
        _lastTargetDistance = calculateDistance(advertisedDevice->getRSSI());
        _lastSeenTime = millis();
    }
}

std::vector<BleDevice> BleManager::scanDevices(uint32_t duration_seconds) {
    std::vector<BleDevice> list;
    NimBLEScan* pScan = NimBLEDevice::getScan();
    
    NimBLEScanResults results = pScan->start(duration_seconds, false);
    for (int i = 0; i < results.getCount(); i++) {
        NimBLEAdvertisedDevice device = results.getDevice(i);
        list.push_back({
            device.getName(),
            device.getAddress().toString(),
            device.getRSSI(),
            calculateDistance(device.getRSSI())
        });
    }
    pScan->clearResults();
    return list;
}

void BleManager::setTargetDevice(std::string name) {
    _targetName = name;
    _lastTargetDistance = -1.0;
}

float BleManager::getTargetDistance() {
    // Se non lo vediamo da troppo tempo, è fuori portata
    if (millis() - _lastSeenTime > _timeoutMs) {
        return -1.0; 
    }
    return _lastTargetDistance;
}