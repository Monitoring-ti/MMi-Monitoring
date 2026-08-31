"""Registro local de trabajos de ingesta (puente hasta ingestion_jobs en Supabase)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("out/ingestion-registry.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_registry(path: Path = DEFAULT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"updated_at": _now(), "jobs": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry(data: dict[str, Any], path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_job(
    entry: dict[str, Any],
    *,
    path: Path = DEFAULT_PATH,
) -> str:
    reg = load_registry(path)
    job_id = entry.get("id") or str(uuid.uuid4())
    entry = {**entry, "id": job_id, "recorded_at": _now()}
    reg["jobs"].append(entry)
    save_registry(reg, path)
    return job_id
