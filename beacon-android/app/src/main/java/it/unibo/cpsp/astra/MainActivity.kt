package it.unibo.cpsp.astra

import android.Manifest
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.ui.Modifier
import it.unibo.cpsp.astra.ui.BeaconScreen
import it.unibo.cpsp.astra.ui.theme.MyApplicationTheme

class MainActivity : ComponentActivity() {

    private val viewModel: BleBeaconViewModel by viewModels()

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { perms ->
        if (perms.values.all { it }) {
            viewModel.refreshDeviceInfo()
        } else {
            Toast.makeText(this, "BLE permissions are required for the beacon", Toast.LENGTH_LONG)
                .show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (!viewModel.isExtendedAdvSupported) {
            Toast.makeText(this, "Extended BLE Advertising not supported", Toast.LENGTH_LONG).show()
            finish()
            return
        }

        requestPermissionLauncher.launch(
            arrayOf(
                Manifest.permission.BLUETOOTH_ADVERTISE,
                Manifest.permission.BLUETOOTH_CONNECT,
            )
        )

        enableEdgeToEdge()
        setContent {
            MyApplicationTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    BeaconScreen(
                        state = viewModel.uiState,
                        onServiceUuidChange = viewModel::onServiceUuidChange,
                        onServiceDataChange = viewModel::onServiceDataChange,
                        onStart = viewModel::startAdvertising,
                        onStop = viewModel::stopAdvertising,
                        modifier = Modifier.padding(innerPadding),
                    )
                }
            }
        }
    }
}
