package it.unibo.cpsp.astra

import android.Manifest
import android.app.Application
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertisingSet
import android.bluetooth.le.AdvertisingSetCallback
import android.bluetooth.le.AdvertisingSetParameters
import android.content.Context
import android.content.pm.PackageManager
import android.os.ParcelUuid
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import java.util.UUID

private const val TAG = "BLE_BEACON"

data class BeaconUiState(
    // Device info
    val deviceName: String = "",
    val bleEnabled: Boolean = false,
    val multiAdvSupported: Boolean = false,
    val extendedAdvSupported: Boolean = false,
    val le2MPhySupported: Boolean = false,
    val leCodedPhySupported: Boolean = false,
    // User inputs
    val serviceUuidInput: String = "00000000-0000-0000-0000-000000000001",
    val serviceDataInput: String = "Hello BLE",
    val uuidError: String? = null,
    // Advertising state
    val isAdvertising: Boolean = false,
    val txPowerLevel: String = "—",
    val interval: String = "—",
    val primaryPhy: String = "—",
    val secondaryPhy: String = "—",
    val activeServiceUuid: String = "—",
    val activeServiceData: String = "—",
)

class BleBeaconViewModel(application: Application) : AndroidViewModel(application) {

    var uiState by mutableStateOf(BeaconUiState())
        private set

    private val bluetoothAdapter by lazy {
        val mgr = application.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
        mgr.adapter
    }

    /** True when the device hardware supports Extended Advertising (required). */
    val isExtendedAdvSupported: Boolean
        get() = bluetoothAdapter?.isLeExtendedAdvertisingSupported ?: false

    init {
        refreshDeviceInfo()
    }

    fun refreshDeviceInfo() {
        val adapter = bluetoothAdapter
        val hasConnectPerm = ContextCompat.checkSelfPermission(
            getApplication(), Manifest.permission.BLUETOOTH_CONNECT
        ) == PackageManager.PERMISSION_GRANTED

        uiState = uiState.copy(
            deviceName = if (hasConnectPerm) adapter?.name ?: "Unknown" else "Permission required",
            bleEnabled = adapter?.isEnabled ?: false,
            multiAdvSupported = adapter?.isMultipleAdvertisementSupported ?: false,
            extendedAdvSupported = adapter?.isLeExtendedAdvertisingSupported ?: false,
            le2MPhySupported = adapter?.isLe2MPhySupported ?: false,
            leCodedPhySupported = adapter?.isLeCodedPhySupported ?: false,
        )
    }

    fun onServiceUuidChange(value: String) {
        val error = if (value.isNotBlank()) {
            try {
                UUID.fromString(value)
                null
            } catch (_: IllegalArgumentException) {
                "Invalid UUID format"
            }
        } else "UUID cannot be empty"
        uiState = uiState.copy(serviceUuidInput = value, uuidError = error)
    }

    fun onServiceDataChange(value: String) {
        uiState = uiState.copy(serviceDataInput = value)
    }

    // ── Advertising ──────────────────────────────────────────────────────────

    private var currentAdvertisingSet: AdvertisingSet? = null

    private val advertisingSetCallback = object : AdvertisingSetCallback() {
        override fun onAdvertisingSetStarted(set: AdvertisingSet?, txPower: Int, status: Int) {
            if (status == ADVERTISE_SUCCESS) {
                currentAdvertisingSet = set
                uiState = uiState.copy(
                    isAdvertising = true,
                    txPowerLevel = "$txPower dBm",
                    interval = "Medium (~250 ms)",
                    primaryPhy = "LE 1M",
                    secondaryPhy = "LE 1M",
                    activeServiceUuid = uiState.serviceUuidInput,
                    activeServiceData = uiState.serviceDataInput,
                )
                Log.d(TAG, "Beacon started, txPower=$txPower")
            } else {
                Log.e(TAG, "Failed to start beacon: status=$status")
            }
        }

        override fun onAdvertisingSetStopped(set: AdvertisingSet?) {
            uiState = uiState.copy(
                isAdvertising = false,
                txPowerLevel = "—",
                interval = "—",
                primaryPhy = "—",
                secondaryPhy = "—",
                activeServiceUuid = "—",
                activeServiceData = "—",
            )
            Log.d(TAG, "Beacon stopped")
        }
    }

    fun startAdvertising() {
        if (uiState.uuidError != null || uiState.serviceUuidInput.isBlank()) return

        val advertiser = bluetoothAdapter?.bluetoothLeAdvertiser ?: run {
            Log.e(TAG, "BLE advertiser not available")
            return
        }

        if (ContextCompat.checkSelfPermission(
                getApplication(), Manifest.permission.BLUETOOTH_ADVERTISE
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            Log.w(TAG, "BLUETOOTH_ADVERTISE permission not granted")
            return
        }

        val params = AdvertisingSetParameters.Builder()
            .setLegacyMode(false)
            .setConnectable(false)
            .setScannable(false)
            .setPrimaryPhy(BluetoothDevice.PHY_LE_1M)
            .setSecondaryPhy(BluetoothDevice.PHY_LE_1M)
            .setInterval(AdvertisingSetParameters.INTERVAL_MEDIUM)
            .setTxPowerLevel(AdvertisingSetParameters.TX_POWER_HIGH)
            .build()

        val serviceUuid = ParcelUuid(UUID.fromString(uiState.serviceUuidInput))
        val serviceData = uiState.serviceDataInput.toByteArray()

        val data = AdvertiseData.Builder()
            .addServiceUuid(serviceUuid)
            .addServiceData(serviceUuid, serviceData)
            .setIncludeTxPowerLevel(true)
            .build()

        advertiser.startAdvertisingSet(params, data, null, null, null, advertisingSetCallback)
    }

    fun stopAdvertising() {
        val advertiser = bluetoothAdapter?.bluetoothLeAdvertiser ?: return
        if (currentAdvertisingSet == null) return
        if (ContextCompat.checkSelfPermission(
                getApplication(), Manifest.permission.BLUETOOTH_ADVERTISE
            ) != PackageManager.PERMISSION_GRANTED
        ) return

        advertiser.stopAdvertisingSet(advertisingSetCallback)
        currentAdvertisingSet = null
    }

    override fun onCleared() {
        super.onCleared()
        stopAdvertising()
    }
}

