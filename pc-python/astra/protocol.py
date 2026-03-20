from __future__ import annotations

import json
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


def cmd_bind(addr: str) -> str:
    """Return the BIND command string for a given BLE address."""
    return f"BIND {addr}"


# ---------------------------------------------------------------------------
# Response dataclasses (parsed from firmware JSON replies)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ScanResult:
    """Result of a SCAN command: list of discovered BLE device addresses."""

    devices: list[str]


@dataclass(slots=True)
class DistanceResult:
    """Result of a DISTANCE command: raw RSSI value in dBm."""

    rssi_dbm: int


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


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProtocolError(ValueError):
    """Raised when a firmware response cannot be parsed."""


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Invalid JSON response: {text!r}") from exc


def parse_scan_response(text: str) -> ScanResult:
    """
    Parse a SCAN response.

    Expected firmware JSON::

        {"result": ["AA:BB:CC:DD:EE:FF", ...]}
    """
    data = _parse_json(text)
    result = data.get("result")
    if not isinstance(result, list):
        raise ProtocolError(
            f"SCAN response: expected a list in 'result', got: {text!r}"
        )
    return ScanResult(devices=[str(d) for d in result])


def parse_distance_response(text: str) -> DistanceResult:
    """
    Parse a DISTANCE response.

    Expected firmware JSON::

        {"result": -72}
    """
    data = _parse_json(text)
    result = data.get("result")
    if result is None:
        raise ProtocolError(f"DISTANCE response: missing 'result' field in: {text!r}")
    try:
        return DistanceResult(rssi_dbm=int(result))
    except (TypeError, ValueError) as exc:
        raise ProtocolError(
            f"DISTANCE response: non-integer RSSI value {result!r}"
        ) from exc
