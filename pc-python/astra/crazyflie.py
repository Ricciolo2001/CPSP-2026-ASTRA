# SPDX-FileCopyrightText: 2026 Alessandro Ricci
# SPDX-FileCopyrightText: 2026 Eyad Issa
# SPDX-FileCopyrightText: 2026 Giulia Pareschi
#
# SPDX-License-Identifier: MIT

import logging
from contextlib import closing

from cflib.drivers.crazyradio import Crazyradio

logger = logging.getLogger(__name__)


ASTRA_PARAM_BOUND_DEVICE_LOW = "astra.bound_device_low"
ASTRA_PARAM_BOUND_DEVICE_HIG = "astra.bound_device_hig"


def get_bound_mac(scf) -> str:
    """Read the currently bound BLE MAC from the Crazyflie params and
    format it as a human-readable string of the form ``'AA:BB:CC:DD:EE:FF'``.
    A MAC of ``'00:00:00:00:00:00'`` indicates no bound device.
    """

    low = int(scf.cf.param.get_value(ASTRA_PARAM_BOUND_DEVICE_LOW))
    high = int(scf.cf.param.get_value(ASTRA_PARAM_BOUND_DEVICE_HIG))

    combined = (high << 32) | low
    mac_bytes = combined.to_bytes(6, byteorder="big")
    return ":".join(f"{b:02X}" for b in mac_bytes)


def set_bound_mac(scf, mac_str: str) -> None:
    """Write a BLE MAC address to the Crazyflie via the param system.

    Accepts ``'AA:BB:CC:DD:EE:FF'`` or ``'AA-BB-CC-DD-EE-FF'`` format.
    Pass ``'00:00:00:00:00:00'`` to unbind.
    """

    parts = mac_str.replace("-", ":").split(":")
    if len(parts) != 6:
        raise ValueError(f"Invalid MAC address: {mac_str!r}")

    mac_bytes = [int(b, 16) for b in parts]
    mac_bytes.reverse()
    low = (
        (mac_bytes[0] << 0)
        | (mac_bytes[1] << 8)
        | (mac_bytes[2] << 16)
        | (mac_bytes[3] << 24)
    )
    high = (mac_bytes[4] << 0) | (mac_bytes[5] << 8)

    # Our Crazyflie FW triggers an event on high param update,
    # so we need to write the low part first, otherwise we might end up with a
    # transient invalid MAC that looks like ``'00:00:CC:DD:EE:FF'``.
    scf.cf.param.set_value(ASTRA_PARAM_BOUND_DEVICE_LOW, str(low))
    scf.cf.param.set_value(ASTRA_PARAM_BOUND_DEVICE_HIG, str(high))


def check_crazyradio():
    try:
        with closing(Crazyradio()):
            return True
    except Exception as e:
        logger.debug(f"Failed to initialize Crazyradio: {e}", exc_info=True)
        return False
