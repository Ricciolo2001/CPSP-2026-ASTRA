#ifndef BLE_MANAGER_H
#define BLE_MANAGER_H

#include <NimBLEDevice.h>
#include <vector>
#include <string>
#include "Struct/BLE_device.h"

class BleManager : public NimBLEAdvertisedDeviceCallbacks {
public:
    BleManager();
    void init();
    
    // Ritorna la lista completa (blocca per duration_seconds)
    std::vector<BleDevice> scanDevices(uint32_t duration_seconds = 5);
    
    // Imposta quale dispositivo monitorare per la distanza immediata
    void setTargetDevice(std::string macAddress);
    
    // Ritorna la distanza dell'ultimo pacchetto ricevuto o -1.0 se fuori portata
    float getTargetDistance();

private:
    // Callback di NimBLE: chiamata ogni volta che un pacchetto arriva nell'etere
    void onResult(NimBLEAdvertisedDevice* advertisedDevice) override;
    float calculateDistance(int rssi);

    std::string _targetAddress;
    float _lastTargetDistance = -1.0;
    unsigned long _lastSeenTime = 0;
    const uint32_t _timeoutMs = 10000; // 10 secondi per considerarlo "Out of Range"
};

#endif