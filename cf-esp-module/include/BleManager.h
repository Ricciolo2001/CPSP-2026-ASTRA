#ifndef BLE_MANAGER_H
#define BLE_MANAGER_H

#include <NimBLEDevice.h>
#include <deque>
#include <string>
#include <vector>

#include "FreeRtosMutex.h"
#include "FreeRtosTask.h"
#include "struct/BleDevice.h"

class BleManager : public NimBLEAdvertisedDeviceCallbacks,
                   public FreeRtosTask<BleManager> {
    friend class FreeRtosTask<BleManager>;

  public:
    BleManager();
    void init();

    // Ritorna la lista completa (blocca per duration_seconds)
    std::vector<BleDevice> scanDevices(uint32_t duration_seconds = 5);

    // Imposta quale dispositivo monitorare per la distanza immediata
    bool setTargetDevice(std::string name);

    // Ritorna la distanza media degli ultimi 5 pacchetti ricevuti o -1.0 se
    // fuori portata
    float getTargetDistance();

  private:
    void run();

  private:
    // Callback di NimBLE: chiamata ogni volta che un pacchetto arriva
    // nell'etere
    void onResult(NimBLEAdvertisedDevice *advertisedDevice) override;
    float calculateDistance(int rssi);

    FreeRtosMutex _mutex; // Protects _targetName, _rssiHistory,
                          // _lastSeenTime, _manualScanInProgress

    std::string _targetName;
    std::deque<int> _rssiHistory;
    unsigned long _lastSeenTime = 0;
    // 10 secondi per considerarlo "Out of Range"
    const uint32_t _timeoutMs = 10000;
    bool _manualScanInProgress = false;
};

#endif
