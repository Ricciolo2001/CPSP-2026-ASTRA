from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# CRTP port used by the ASTRA firmware app
# ---------------------------------------------------------------------------

CRTP_APP_PORT: int = 0x0E

# ---------------------------------------------------------------------------
# Commands (text strings sent to the firmware)
# ---------------------------------------------------------------------------

CMD_SCAN = "SCAN"
CMD_DISTANCE = "DISTANCE"


# ---------------------------------------------------------------------------
# Response dataclasses (parsed from firmware JSON replies)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Telemetry:
    """
    Combined sample collected during a flight: drone position (from the
    Crazyflie state estimator) plus beacon RSSI (from DISTANCE command).
    """

    x: float
    y: float
    yaw: float
    rssi: int
