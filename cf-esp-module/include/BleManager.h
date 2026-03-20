#ifndef BLE_MANAGER_H
#define BLE_MANAGER_H

#include <NimBLEDevice.h>
#include <atomic>
#include <string>
#include <vector>

#include "EwmaFilter.hpp"
#include "freertos/semaphore.hpp"
#include <freertos/queue.h>

extern "C" {
#include "astra_protocol.h"
}

/// Represents a BLE device found during scanning.
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

/// Manages BLE scanning and tracking of a target device's RSSI.
///
/// Remember to call `init()` before using, otherwise the behavior is undefined.
///
/// This class is a singleton that interfaces with the NimBLE library to perform
/// BLE scans. It supports both continuous background scanning (for tracking a
/// target device) and on-demand active scanning (for device discovery).
///
/// Active scanning is more power-intensive and sends scan requests to nearby
/// devices to retrieve additional information like full device names.
/// Background scanning is more power-efficient and only listens for
/// advertisements without sending scan requests.
class BleManager : public NimBLEAdvertisedDeviceCallbacks {
  public:
    /// Returns the singleton instance of BleManager.
    ///
    /// The first call to this function will construct the instance. Subsequent
    /// calls will return the same instance.
    ///
    /// The instance is never destroyed, so it will remain valid for the
    /// lifetime of the program.
    static BleManager &instance();

    // Non-copyable, non-movable.
    BleManager(const BleManager &) = delete;
    BleManager &operator=(const BleManager &) = delete;

    ~BleManager();

    /// Start the background BLE scan.
    /// This will run indefinitely until stopBackgroundScan() is called.
    void startBackgroundScan();

    /// Stop the background BLE scan.
    /// This will block until the scan has fully stopped.
    void stopBackgroundScan();

    /// Perform a one-time active scan for nearby BLE devices. Blocks until the
    /// scan completes (or times out) and returns the list of devices found.
    std::vector<BleDevice> scanDevices(uint32_t duration_seconds = 5);

    /// Set the target device by its BLE address (e.g. "AA:BB:CC:DD:EE:FF").
    ///
    /// After setting the target device, the manager will track its RSSI in the
    /// background and make it available via getTargetRssi().
    void setTargetDevice(std::string addr);
    void clearTargetDevice();

    /// Receive the next RSSI observation pushed by the BLE scan callback.
    /// Blocks for at most @p timeout ticks; returns pdTRUE on success.
    BaseType_t receiveRssi(astra_uart_rssi_value_t *out, TickType_t timeout);

    /// Get the current RSSI of the target device.
    ///
    /// Returns the smoothed RSSI value based on recent samples.
    /// If the target device was never seen or hasn't been seen for a while,
    /// returns -1.
    float getTargetRssi();

  private:
    BleManager();

    enum class ScanMode {
        // Passive, low duty cycle used during normal flight.
        Background,
        // Active, high duty cycle used for device discovery.
        // Sends scan requests to retrieve full device names.
        Discovery,
    };

    /// Configure the NimBLE scan parameters based on the desired scan mode.
    void applyScanParams(ScanMode mode);
    /// Callback invoked by NimBLE for each advertisement received during
    /// scanning.
    void onResult(NimBLEAdvertisedDevice *advertisedDevice) override;

    /// Callbacks invoked by NimBLE when a scan cycle completes.
    static void onBgScanComplete(NimBLEScanResults results);
    static void onManualScanComplete(NimBLEScanResults results);

    // Target related state

    freertos::Mutex _targetMutex;
    std::string _targetAddr;
    EwmaFilter<float> _targetRssiFilter;
    unsigned long _targetLastSeenTime = 0;
    const uint32_t _timeoutMs = 10000;

    /// While true, the background scan is active and onBgScanComplete should
    /// restart itself. When set to false, onBgScanComplete will signal that the
    /// background scan has fully stopped.
    std::atomic<bool> _bgScanActive{false};
    const uint32_t _bgScanPeriodMs = 1000;

    // Signalled by onBgScanComplete when it decides NOT to restart (bg scan
    // fully stopped).
    freertos::BinarySemaphore _bgScanStopped;
    // Signalled by onManualScanComplete when the manual scan finishes.
    freertos::BinarySemaphore _manualScanDone;
    std::vector<BleDevice> _manualScanResults;

    static constexpr int kRssiQueueLen = 16;
    QueueHandle_t _rssiQueue = nullptr;
};

#endif
