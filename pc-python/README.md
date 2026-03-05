Python code for the PC side of the ASTRA project.

This module will handle:
- receiving packets from Crazyflie
- RSSI filtering
- beacon localization

## Run

Install dependencies

pip install -r requirements.txt

Run receiver

cd pc-python
python scripts/receive_appchannel.py
