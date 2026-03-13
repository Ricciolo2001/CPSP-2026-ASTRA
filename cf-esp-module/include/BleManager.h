#ifndef BLE_MANAGER_H
#define BLE_MANAGER_H

#include <NimBLEDevice.h>
#include <atomic>
#include <deque>
#include <string>
#include <variant>
#include <vector>

#include "freertos/semaphore.hpp"

struct BleDevice {
    std::string name;
    std::string address;
    int rssi;
    std::string serviceUUID; // The primary Service UUID
    std::string serviceData; // Hex-encoded or raw data

    BleDevice(std::string n, std::string a, int r, std::string su = "",
              std::string sd = "")
        : name(std::move(n)), address(std::move(a)), rssi(r),
          serviceUUID(std::move(su)), serviceData(std::move(sd)) {}
};

class RssiFilter {
  public:
    // alpha: 0.0 to 1.0.
    // Higher = more responsive (less smooth). Lower = slower (smoother).
    explicit RssiFilter(float alpha = 0.2f) : alpha_(alpha) {}

    void update(float newSample);
    float get() const { return currentAverage_; }

  private:
    float alpha_;
    float currentAverage_ = 0.0f;
    bool isFirstSample_ = true;
};

class BleManager : public NimBLEAdvertisedDeviceCallbacks {
  public:
    static BleManager &instance();

    // Non-copyable, non-movable.
    BleManager(const BleManager &) = delete;
    BleManager &operator=(const BleManager &) = delete;

    ~BleManager();

    void init();

    // Start/stop the continuous background BLE scan.
    void startBackgroundScan();
    void stopBackgroundScan();

    // Pause background scan, perform a full N-second scan, return all devices.
    // active=true uses a 99% duty cycle; active=false uses the default 50/200.
    std::vector<BleDevice> scanDevices(uint32_t duration_seconds = 5,
                                       bool active = true);

    // Set which device to track for real-time distance estimation.
    bool setTargetDevice(std::string name);

    // Returns averaged RSSI, or -1.0 if out of range.
    float getTargetRssi();

  private:
    BleManager() = default;

    void applyScanParams(bool active);
    void onResult(NimBLEAdvertisedDevice *advertisedDevice) override;

    // Scan-complete callbacks invoked by NimBLE on Core 0.
    static void onBgScanComplete(NimBLEScanResults results);
    static void onManualScanComplete(NimBLEScanResults results);

    // Protects _targetName, _rssiHistory, _lastSeenTime.
    freertos::Mutex _mutex;

    std::string _targetName;
    RssiFilter _targetRssiFilter;
    unsigned long _targetLastSeenTime = 0;
    const uint32_t _timeoutMs = 10000;

    std::atomic<bool> _bgScanActive{false};
    // Signalled by onBgScanComplete when it decides NOT to restart (bg scan
    // fully stopped).
    freertos::BinarySemaphore _bgScanStopped;
    // Signalled by onManualScanComplete when the manual scan finishes.
    freertos::BinarySemaphore _manualScanDone;
    std::vector<BleDevice> _manualScanResults;
};

#endif
