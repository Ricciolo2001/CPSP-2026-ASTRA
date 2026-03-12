# ASTRA pc-python

Python code for the PC side of the ASTRA project.

This module handles:
- receiving packets from Crazyflie AppChannel
- RSSI filtering
- telemetry logging to CSV
- offline beacon localization from a CSV log

## Packet format

Current packet format is aligned with the placeholder already present in the repository:

```python
DEFAULT_FMT = "<fffhH"
```

Fields:
- `x`   : `float32`
- `y`   : `float32`
- `yaw` : `float32`
- `rssi`: `int16`
- `seq` : `uint16`

If the firmware sends a different payload, update `astra/protocol.py`.

## Installation

```bash
cd pc-python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Receive telemetry

```bash
python scripts/receive_appchannel.py --uri radio://0/80/2M/E7E7E7E7E7
```

## Log telemetry to CSV

```bash
python scripts/log_csv.py --uri radio://0/80/2M/E7E7E7E7E7 --out telemetry_log.csv
```

Generated CSV header:

```text
t,x,y,yaw,rssi_raw,rssi_filtered,seq
```

## Localize beacon from CSV

```bash
python scripts/localize_csv.py telemetry_log.csv --plot
```

Useful calibration parameters:
- `--tx-power`: beacon RSSI at 1 meter
- `--path-loss`: path loss exponent of the environment

Example:

```bash
python scripts/localize_csv.py telemetry_log.csv --tx-power -62 --path-loss 2.3 --plot
```
Before testing on the real drone, verify that the Crazyflie firmware really sends packets in the format `<fffhH`. If not, only `astra/protocol.py` must be updated.
