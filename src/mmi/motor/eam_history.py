"""Histórico EAM / CMMS (fixture → API producción)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

_DEFAULT_FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "motor-eam.json"


def load_eam_fixture(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or _DEFAULT_FIXTURE
    if not fixture_path.is_file():
        return {"calibrations": [], "work_orders": [], "doc_conflicts": []}
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _parse_date(raw: str) -> date:
    return datetime.fromisoformat(raw.strip()).date()


def _asset_match(row_asset: str, asset_id: str) -> bool:
    return (row_asset or "").strip().upper() == (asset_id or "").strip().upper()


def get_calibrations(asset_id: str, *, fixture: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = fixture if fixture is not None else load_eam_fixture()
    return [dict(row) for row in data.get("calibrations") or [] if _asset_match(row.get("asset_id", ""), asset_id)]


def get_work_orders(asset_id: str, *, fixture: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = fixture if fixture is not None else load_eam_fixture()
    rows = [dict(row) for row in data.get("work_orders") or [] if _asset_match(row.get("asset_id", ""), asset_id)]
    rows.sort(key=lambda r: r.get("date") or "", reverse=True)
    return rows


def get_doc_conflicts(asset_id: str, *, fixture: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = fixture if fixture is not None else load_eam_fixture()
    return [dict(row) for row in data.get("doc_conflicts") or [] if _asset_match(row.get("asset_id", ""), asset_id)]


def match_work_orders_by_symptom(
    work_orders: list[dict[str, Any]],
    symptom: str,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """WO relevantes por coincidencia de síntoma (piloto)."""
    symptom_l = (symptom or "").lower()
    if not symptom_l:
        return work_orders[:limit]

    scored: list[tuple[int, dict[str, Any]]] = []
    for wo in work_orders:
        score = 0
        for token in symptom_l.replace(",", " ").split():
            if len(token) < 4:
                continue
            for s in wo.get("symptoms") or []:
                if token in s.lower() or s.lower() in symptom_l:
                    score += 2
        if wo.get("wo_code"):
            score += 1
        scored.append((score, wo))

    scored.sort(key=lambda x: x[0], reverse=True)
    if scored and scored[0][0] > 0:
        return [wo for _, wo in scored[:limit]]
    return work_orders[:limit]


def build_eam_history_payload(
    asset_id: str,
    symptom: str,
    *,
    fixture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    work_orders = get_work_orders(asset_id, fixture=fixture)
    relevant = match_work_orders_by_symptom(work_orders, symptom)
    calibrations = get_calibrations(asset_id, fixture=fixture)
    return {
        "asset_id": asset_id,
        "work_orders": relevant,
        "work_order_count": len(work_orders),
        "calibrations": calibrations,
    }
