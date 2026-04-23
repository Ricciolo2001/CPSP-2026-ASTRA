# SPDX-FileCopyrightText: 2026 Alessandro Ricci
# SPDX-FileCopyrightText: 2026 Eyad Issa
# SPDX-FileCopyrightText: 2026 Giulia Pareschi
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import threading
from typing import Callable


class LineBuffer:
    """
    Reassemble lines of text from a stream of UTF-8 text chunks, and call a
    callback for each complete line.

    Use feed() to add text chunks to the buffer, the callback will be called
    for each complete line that can be extracted from the buffer, excluding
    the newline character.
    """

    def __init__(self, on_line: Callable[[str], None]) -> None:
        self._buf = ""
        self._on_line = on_line
        self._lock = threading.Lock()

    def feed(self, text: str) -> None:
        to_emit = []
        with self._lock:
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                to_emit.append(line)

        for line in to_emit:
            self._on_line(line)


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
