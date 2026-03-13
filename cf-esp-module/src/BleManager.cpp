#include "BleManager.h"

#include <mutex>

#include "freertos/mutex.hpp"
#include "freertos/task.hpp"

const int MEASURED_POWER = -60;
const float N_FACTOR = 2.5;

// ! Da calibrare per il singolo sensore, guardare una guida su come fare (la
// calibrazione andrebbe fatta ad un metro di distnaza) ! Ovviamente le board
// che usiamo sono merdose, no shielding e no rf matching (catena di induttori e
// condensatori) quindi non avremo risultati solidi... ! Nell'AI deck invece c'è
// un RF matching fatto bene, e un bellissimo shield per le interferenze...

BleManager::BleManager()
    : freertos::Task<BleManager>({"BLEScan", 4096, 1}), _targetName(""),
      _rssiHistory(), _mutex() {}

void BleManager::init() {
    NimBLEDevice::init("");
    NimBLEScan *pScan = NimBLEDevice::getScan();
    pScan->setAdvertisedDeviceCallbacks(this, false);
    pScan->setActiveScan(true);
    pScan->setInterval(45); // Più veloce per non perdere pacchetti
    pScan->setWindow(15);

    start(); // launch the continuous background scan task
}

float BleManager::calculateDistance(int rssi) {
    if (rssi == 0)
        return -1.0;
    return pow(10, (float)(MEASURED_POWER - rssi) / (10 * N_FACTOR));
}

void BleManager::onResult(NimBLEAdvertisedDevice *advertisedDevice) {
    std::lock_guard lock(_mutex);

    // Se è il dispositivo che stiamo monitorando, aggiorniamo la storia RSSI
    if (_targetName != "" && advertisedDevice->getName() == _targetName) {
        _rssiHistory.push_back(advertisedDevice->getRSSI());
        if (_rssiHistory.size() > 5)
            _rssiHistory.pop_front();
        _lastSeenTime = millis();
    }
}

std::vector<BleDevice> BleManager::scanDevices(uint32_t duration_seconds) {
    NimBLEScan *pScan = NimBLEDevice::getScan();

    pScan->stop(); // Stop the background scan

    {
        std::lock_guard lock(_mutex);
        _manualScanInProgress = true;
    }

    // Start the manual scan
    NimBLEScanResults results = pScan->start(duration_seconds, false);

    {
        std::lock_guard lock{_mutex};
        _manualScanInProgress = false;
    }

    // Data to send back to caller
    std::vector<BleDevice> list;
    for (int i = 0; i < results.getCount(); i++) {
        NimBLEAdvertisedDevice device = results.getDevice(i);
        list.push_back({device.getName(), device.getAddress().toString(),
                        device.getRSSI(), calculateDistance(device.getRSSI())});
    }
    pScan->clearResults();

    return list;
}

bool BleManager::setTargetDevice(std::string name) {
    std::lock_guard lock(_mutex);

    // TODO: Look if the device exist!
    _targetName = name;
    _rssiHistory.clear();
    return true;
}

float BleManager::getTargetDistance() {
    std::lock_guard lock(_mutex);
    // Se non abbiamo almeno 5 misurazioni o è passato troppo tempo, fuori
    // portata
    if (_rssiHistory.size() < 5 || millis() - _lastSeenTime > _timeoutMs) {
        return -1.0;
    }

    // Calcola la media delle ultime 5 distanze
    float sum = 0.0;
    for (int rssi : _rssiHistory) {
        sum += calculateDistance(rssi);
    }
    return sum / 5.0;
}

void BleManager::run() {
    while (running_.load(std::memory_order_relaxed)) {
        bool pause = false;
        {
            std::lock_guard lock(_mutex);
            pause = _manualScanInProgress;
        }
        if (!pause) {
            NimBLEDevice::getScan()->start(1, false); // Scan for one second
        }
        vTaskDelay(100 / portTICK_PERIOD_MS); // Pausa di 100ms
    }
}
