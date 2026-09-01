"""Metadatos de exportación / impresión Motor MMI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mmi.motor.analyze import MotorAnalysisResult


def build_export_meta(
    result: MotorAnalysisResult,
    motor_id: str,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    ts = generated_at or datetime.now(timezone.utc)
    source_ids: list[str] = []
    for ref in result.references:
        doc_id = ref.get("document_id")
        if doc_id and doc_id not in source_ids:
            source_ids.append(doc_id)

    return {
        "motor_id": motor_id,
        "asset_id": result.asset.get("id") or "",
        "asset_name": result.asset.get("name") or "",
        "symptom": result.symptom,
        "window": result.window,
        "model": result.model,
        "generated_at": ts.isoformat().replace("+00:00", "Z"),
        "source_ids": source_ids,
        "source_count": len(source_ids),
    }
