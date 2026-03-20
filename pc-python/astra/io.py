from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping

CSV_HEADER = ["t", "x", "y", "yaw", "rssi_raw", "rssi_filtered"]


def write_csv_rows(path: str | Path, rows: Iterable[Mapping[str, object]]) -> None:
    path = Path(path)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_csv_rows(path: str | Path) -> list[dict[str, float]]:
    path = Path(path)
    out: list[dict[str, float]] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append(
                {
                    "t": float(row["t"]),
                    "x": float(row["x"]),
                    "y": float(row["y"]),
                    "yaw": float(row["yaw"]),
                    "rssi_raw": float(row["rssi_raw"]),
                    "rssi_filtered": float(row["rssi_filtered"]),
                }
            )
    return out
