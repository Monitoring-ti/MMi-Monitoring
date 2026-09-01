"""Adapter de lecturas de sensores (fixture → PI)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_DEFAULT_FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "motor-sensors.json"

_WINDOW_HOURS = {"24h": 24, "7d": 168, "30d": 720}


@dataclass(frozen=True)
class SensorReading:
    asset_id: str
    tag: str
    description: str
    value: float
    unit: str
    timestamp: datetime
    nominal: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "tag": self.tag,
            "description": self.description,
            "value": self.value,
            "unit": self.unit,
            "nominal": self.nominal,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
        }


def load_sensor_fixture(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or _DEFAULT_FIXTURE
    if not fixture_path.is_file():
        return {"readings": []}
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _parse_ts(raw: str) -> datetime:
    text = (raw or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _in_window(ts: datetime, window: str, *, now: datetime | None = None) -> bool:
    if window == "custom":
        return True
    hours = _WINDOW_HOURS.get(window, 24)
    ref = now or datetime.now(timezone.utc)
    return ts >= ref - timedelta(hours=hours)


def get_sensor_readings(
    asset_id: str,
    *,
    window: str = "24h",
    fixture: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> list[SensorReading]:
    """Lecturas PI/SCADA del activo en la ventana temporal (fixture en piloto)."""
    data = fixture if fixture is not None else load_sensor_fixture()
    tag = (asset_id or "").strip().upper()
    out: list[SensorReading] = []
    for row in data.get("readings") or []:
        if (row.get("asset_id") or "").strip().upper() != tag:
            continue
        ts = _parse_ts(row.get("timestamp") or "")
        if not _in_window(ts, window, now=now):
            continue
        out.append(
            SensorReading(
                asset_id=tag,
                tag=row.get("tag") or "",
                description=row.get("description") or "",
                value=float(row.get("value") or 0),
                unit=row.get("unit") or "",
                nominal=float(row["nominal"]) if row.get("nominal") is not None else None,
                timestamp=ts,
            )
        )
    return out
