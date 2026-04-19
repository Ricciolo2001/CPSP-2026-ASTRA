# ASTRA pc-python

Python code for the PC side of the ASTRA project.

This module handles:
- sending commands to the Crazyflie firmware via CRTP (text/JSON protocol)
- receiving beacon RSSI via the `DISTANCE` command
- receiving drone position via the cflib log framework (state estimator)
- RSSI filtering (median + EMA)
- telemetry logging to CSV
- offline beacon localization from a CSV log

---

## Protocol

Communication with the firmware uses a **text-based JSON protocol** over CRTP port `0x0E`.
Messages are UTF-8 lines (newline-terminated) and are chunked across CRTP packets
(max 30 bytes each) by `send_line` / `LineAssembler`.

### Commands (PC → firmware)

| Command | Description |
|---------|-------------|
| `SCAN` | Scan for nearby BLE devices |
| `BIND <addr>` | Bind to the BLE beacon at the given address |
| `DISTANCE` | Request the current RSSI of the bound beacon |

### Responses (firmware → PC)

All responses are JSON objects with a `"result"` field.

```json
// SCAN response
{"result": ["AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"]}

// DISTANCE response
{"result": -72}
```

### Drone position

Position (`x`, `y`, `yaw`) is streamed independently via the **cflib log framework**
(`stateEstimate.x`, `stateEstimate.y`, `stateEstimate.yaw` at 10 Hz).
No firmware changes are required for this — it uses the standard Crazyflie log variables.

---

## Package layout

```
astra/
  __init__.py
  __main__.py          # Interactive CRTP console (SCAN / BIND / DISTANCE / free text)
  protocol.py          # Command constants, response parsers, Telemetry dataclass
  crazyflie.py         # send_line, LineAssembler, FirmwareLogAssembler, AstraLink
  rssi.py              # MedianEmaFilter, rssi_to_distance
  localization.py      # estimate_beacon_position (grid search + Gauss-Newton)
  io.py                # CSV read/write helpers

scripts/
  receive_appchannel.py   # Print telemetry samples in real time
  log_csv.py              # Log telemetry samples to CSV
  localize_csv.py         # Estimate beacon position from a CSV log
```

---

## Installation

```bash
cd pc-python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Interactive console

The main entry point is an interactive console that sends raw commands to the firmware
and displays its responses.

```bash
# Default mode: free-text CRTP console
python -m astra --uri radio://0/80/2M/E7E7E7E7E7

# Scan for BLE beacons and exit
python -m astra --uri radio://0/80/2M/E7E7E7E7E7 --scan

# Bind to a beacon and poll its distance every 500 ms
python -m astra --uri radio://0/80/2M/E7E7E7E7E7 --bind AA:BB:CC:DD:EE:FF
```

Firmware `DEBUG_PRINT` output is forwarded to the console with a `[CF]` prefix.

---

## Receive telemetry (real time)

```bash
python scripts/receive_appchannel.py \
    --uri radio://0/80/2M/E7E7E7E7E7 \
    --beacon AA:BB:CC:DD:EE:FF
```

Each sample prints: `x`, `y`, `yaw` (from state estimator) and `rssi` (from DISTANCE command).

---

## Log telemetry to CSV

```bash
python scripts/log_csv.py \
    --uri radio://0/80/2M/E7E7E7E7E7 \
    --beacon AA:BB:CC:DD:EE:FF \
    --out telemetry_log.csv
```

Optional arguments:

| Flag | Default | Description |
|------|---------|-------------|
| `--poll` | `0.5` | DISTANCE polling interval in seconds |
| `--window` | `5` | Median filter window size |
| `--alpha` | `0.35` | EMA smoothing factor |

Generated CSV header:

```
t,x,y,yaw,rssi_raw,rssi_filtered
```

---

## Localize beacon from CSV

```bash
python scripts/localize_csv.py telemetry_log.csv --plot
```

Useful calibration parameters:

| Flag | Default | Description |
|------|---------|-------------|
| `--tx-power` | `-40.0` | Beacon RSSI at 1 metre [dBm] |
| `--path-loss` | `2.0` | Path loss exponent |

Example with custom calibration:

```bash
python scripts/localize_csv.py telemetry_log.csv \
    --tx-power -40 --path-loss 2.3 --plot
```

The localization algorithm:
1. Converts filtered RSSI samples to distances using the log-distance path loss model.
2. Performs a coarse 2D grid search within the explored bounding box.
3. Refines the result with Gauss-Newton least squares.

Output includes estimated position `(x, y)` and RMSE in metres.

---

## RSSI filter

Samples pass through a two-stage filter in `astra/rssi.py`:

1. **Running median** over a sliding window (removes impulsive noise).
2. **Exponential Moving Average (EMA)** for temporal smoothing.

Default parameters match `log_csv.py`: `window=5`, `alpha=0.35`.

---

## Notes

- The `tx_power` default (`-40 dBm`) must be calibrated empirically by measuring the
  actual RSSI of the target beacon at exactly 1 metre in the test environment.
- The `path_loss_n` exponent depends on the environment: `2.0` is free space,
  higher values (2.5–4.0) model indoor obstructions.
- Before flight, verify that the firmware responds to `SCAN`, `BIND`, and `DISTANCE`
  commands with the expected JSON format. Only `astra/protocol.py` needs updating
  if the response format changes.
