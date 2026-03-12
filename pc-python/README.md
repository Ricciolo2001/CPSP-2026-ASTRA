# ASTRA pc-python

Python code for the PC side of the ASTRA project.

This module handles:
- receiving packets from Crazyflie AppChannel
- RSSI filtering
- telemetry logging to CSV
- offline beacon localization from a CSV log

## Folder structure

```text
pc-python/
├── astra/
│   ├── __init__.py
│   ├── protocol.py
│   ├── crazyflie_link.py
│   ├── io.py
│   ├── localization.py
│   └── rssi.py
├── scripts/
│   ├── log_csv.py
│   ├── localize_csv.py
│   └── receive_appchannel.py
├── README.md
└── requirements.txt
```

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

## Notes for repository integration

This version is designed to fit directly into the current repository structure:
- it keeps `astra/__init__.py`
- it replaces the placeholder `astra/protocol.py`
- it keeps and improves `scripts/receive_appchannel.py`
- it keeps and improves `scripts/log_csv.py`
- it adds the missing modules needed for filtering and localization

## Recommended next check with the team

Before testing on the real drone, verify that the Crazyflie firmware really sends packets in the format `<fffhH`. If not, only `astra/protocol.py` must be updated.
