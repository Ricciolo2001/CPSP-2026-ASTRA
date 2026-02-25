package it.unibo.cpsp.astra.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.BluetoothDisabled
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import it.unibo.cpsp.astra.BeaconUiState

@Composable
fun BeaconScreen(
    state: BeaconUiState,
    onServiceUuidChange: (String) -> Unit,
    onServiceDataChange: (String) -> Unit,
    onStart: () -> Unit,
    onStop: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        if (!state.extendedAdvSupported) {
            UnsupportedCard()
        } else {
            BeaconControlCard(
                state = state,
                onServiceUuidChange = onServiceUuidChange,
                onServiceDataChange = onServiceDataChange,
                onStart = onStart,
                onStop = onStop,
            )
            BluetoothInfoCard(state)
        }
    }
}

@Composable
private fun BeaconControlCard(
    state: BeaconUiState,
    onServiceUuidChange: (String) -> Unit,
    onServiceDataChange: (String) -> Unit,
    onStart: () -> Unit,
    onStop: () -> Unit,
) {
    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.extraLarge,
        colors = CardDefaults.elevatedCardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier.padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(24.dp),
        ) {
            StatusIndicator(state.isAdvertising)

            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = if (state.isAdvertising) "Beacon Active" else "Beacon Offline",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = if (state.isAdvertising) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.outline
                    },
                )
                Text(
                    text = if (state.isAdvertising) "Broadcasting BLE signal…" else "Ready to transmit",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            HorizontalDivider(modifier = Modifier.alpha(0.5f))

            OutlinedTextField(
                value = state.serviceUuidInput,
                onValueChange = onServiceUuidChange,
                label = { Text("Service UUID") },
                placeholder = { Text("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx") },
                isError = state.uuidError != null,
                supportingText = state.uuidError?.let { { Text(it) } },
                enabled = !state.isAdvertising,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )

            OutlinedTextField(
                value = state.serviceDataInput,
                onValueChange = onServiceDataChange,
                label = { Text("Service Data") },
                placeholder = { Text("e.g. Hello BLE") },
                enabled = !state.isAdvertising,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Button(
                    onClick = onStart,
                    enabled = !state.isAdvertising && state.uuidError == null,
                    modifier = Modifier.weight(1f),
                    shape = MaterialTheme.shapes.medium,
                    contentPadding = PaddingValues(16.dp),
                ) {
                    Text("START", fontWeight = FontWeight.Bold)
                }
                OutlinedButton(
                    onClick = onStop,
                    enabled = state.isAdvertising,
                    modifier = Modifier.weight(1f),
                    shape = MaterialTheme.shapes.medium,
                    contentPadding = PaddingValues(16.dp),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.error,
                    ),
                ) {
                    Text("STOP", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun BluetoothInfoCard(state: BeaconUiState) {
    ElevatedCard(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.extraLarge,
        colors = CardDefaults.elevatedCardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(
            modifier = Modifier.padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "Bluetooth Info",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))

            InfoRow("Device Name", state.deviceName)
            InfoRow("BLE Enabled", if (state.bleEnabled) "Yes" else "No")
            InfoRow("Multiple Advertising", if (state.multiAdvSupported) "Supported" else "Not supported")
            InfoRow("Extended Advertising", if (state.extendedAdvSupported) "Supported" else "Not supported")
            InfoRow("LE 2M PHY", if (state.le2MPhySupported) "Supported" else "Not supported")
            InfoRow("LE Coded PHY", if (state.leCodedPhySupported) "Supported" else "Not supported")

            if (state.isAdvertising) {
                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))
                Text(
                    text = "Active Advertisement",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.primary,
                )
                InfoRow("TX Power", state.txPowerLevel)
                InfoRow("Interval", state.interval)
                InfoRow("Primary PHY", state.primaryPhy)
                InfoRow("Secondary PHY", state.secondaryPhy)
                InfoRow("Service UUID", state.activeServiceUuid)
                InfoRow("Service Data", state.activeServiceData)
            }
        }
    }
}

@Composable
private fun StatusIndicator(isActive: Boolean) {
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.3f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "alpha",
    )
    val color by animateColorAsState(
        targetValue = if (isActive) MaterialTheme.colorScheme.primary else Color.LightGray,
        label = "statusColor",
    )

    Box(contentAlignment = Alignment.Center) {
        if (isActive) {
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .background(color.copy(alpha = pulseAlpha * 0.2f), CircleShape),
            )
        }
        Surface(
            modifier = Modifier.size(64.dp),
            shape = CircleShape,
            color = color,
            tonalElevation = 4.dp,
        ) {
            Icon(
                imageVector = Icons.Default.Bluetooth,
                contentDescription = if (isActive) "Beacon active" else "Beacon inactive",
                modifier = Modifier
                    .padding(16.dp)
                    .fillMaxSize(),
                tint = Color.White,
            )
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f),
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun UnsupportedCard() {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = Icons.Default.BluetoothDisabled,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.error,
            )
            Spacer(Modifier.width(12.dp))
            Text(
                "Extended BLE Advertising is not supported on this device.",
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
        }
    }
}

