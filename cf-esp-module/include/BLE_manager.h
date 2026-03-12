#ifndef BLE_MANAGER_H
#define BLE_MANAGER_H

#include <NimBLEDevice.h>
#include <vector>
#include <string>
#include <deque>
#include "Struct/BLE_device.h"

class BleManager : public NimBLEAdvertisedDeviceCallbacks
{
public:
    BleManager();
    void init();

    // Ritorna la lista completa (blocca per duration_seconds)
    std::vector<BleDevice> scanDevices(uint32_t duration_seconds = 5);

    // Imposta quale dispositivo monitorare per la distanza immediata
    bool setTargetDevice(std::string name);

    // Ritorna la distanza media degli ultimi 5 pacchetti ricevuti o -1.0 se fuori portata
    float getTargetDistance();

protected:
    static void runTask(void* pvParameters);
    void run();

private:
    // Callback di NimBLE: chiamata ogni volta che un pacchetto arriva nell'etere
    void onResult(NimBLEAdvertisedDevice *advertisedDevice) override;
    float calculateDistance(int rssi);

    std::string _targetName;
    std::deque<int> _rssiHistory;
    unsigned long _lastSeenTime = 0;
    const uint32_t _timeoutMs = 10000; // 10 secondi per considerarlo "Out of Range"
    bool _manualScanInProgress = false;
};

#endif