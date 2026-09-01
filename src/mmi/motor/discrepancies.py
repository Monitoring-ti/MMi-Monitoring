"""Detección de discrepancias: calibración, EAM, conflictos documentales (C2 stub)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from mmi.motor.eam_history import (
    get_calibrations,
    get_doc_conflicts,
    get_work_orders,
    match_work_orders_by_symptom,
)
from mmi.search.engine import SearchResult

_DEFAULT_RULES = Path(__file__).resolve().parents[3] / "fixtures" / "motor-discrepancies.json"


def load_discrepancy_rules(path: Path | None = None) -> dict[str, Any]:
    rules_path = path or _DEFAULT_RULES
    if not rules_path.is_file():
        return {"calibration_max_days": 365, "reading_tolerance_pct": 5, "rules": {}}
    return json.loads(rules_path.read_text(encoding="utf-8"))


def _days_since(iso_date: str, *, today: date | None = None) -> int:
    ref = today or datetime.now(timezone.utc).date()
    try:
        dt = _parse_date(iso_date)
    except ValueError:
        return 0
    return (ref - dt).days


def _parse_date(raw: str) -> date:
    return datetime.fromisoformat(raw.strip()).date()


def _validate_discrepancy(raw: dict[str, Any]) -> dict[str, Any] | None:
    text = (raw.get("text") or "").strip()
    if not text:
        return None
    severity = (raw.get("severity") or "warn").strip().lower()
    if severity not in {"warn", "info", "error"}:
        severity = "warn"
    return {
        "text": text,
        "severity": severity,
        "rule": (raw.get("rule") or "llm").strip(),
        "kind": (raw.get("kind") or "general").strip(),
    }


def detect_calibration_discrepancies(
    asset_id: str,
    *,
    rules: dict[str, Any],
    today: date | None = None,
) -> list[dict[str, Any]]:
    if not rules.get("rules", {}).get("calibration_overdue", True):
        return []
    max_days = int(rules.get("calibration_max_days") or 365)
    tol = float(rules.get("reading_tolerance_pct") or 5)
    out: list[dict[str, Any]] = []

    for cal in get_calibrations(asset_id):
        days = _days_since(cal.get("last_calibration") or "", today=today)
        interval = int(cal.get("interval_days") or max_days)
        overdue = days > interval
        drift = float(cal.get("reading_drift_pct") or 0)
        drift_exceeded = drift > tol

        if overdue or drift_exceeded:
            tag = cal.get("tag") or "instrumento"
            parts = []
            if overdue:
                parts.append(f"última calibración hace {days} días (máx {interval})")
            if drift_exceeded:
                parts.append(f"lectura ±{drift:g}% fuera de tolerancia ±{tol:g}%")
            out.append(
                {
                    "text": f"{tag} — {'; '.join(parts)}",
                    "severity": "warn" if overdue else "info",
                    "rule": "calibration_overdue",
                    "kind": "metrology",
                    "tag": tag,
                }
            )
    return out


def detect_wo_discrepancies(
    asset_id: str,
    symptom: str,
    facts: list[dict[str, Any]],
    *,
    rules: dict[str, Any],
) -> list[dict[str, Any]]:
    if not rules.get("rules", {}).get("reading_vs_wo", True):
        return []
    work_orders = get_work_orders(asset_id)
    relevant = match_work_orders_by_symptom(work_orders, symptom)
    if not relevant:
        return []

    out: list[dict[str, Any]] = []
    top = relevant[0]
    wo_code = top.get("wo_code") or "WO"
    mtbf = top.get("mtbf_hours")
    expected = top.get("mtbf_expected_hours")
    if mtbf is not None and expected is not None and mtbf < expected * 0.85:
        out.append(
            {
                "text": (
                    f"{wo_code} ({top.get('date', '')}): MTBF {mtbf} h vs esperado {expected} h "
                    f"— causa previa: {top.get('cause', '')}"
                ),
                "severity": "info",
                "rule": "reading_vs_wo",
                "kind": "eam_history",
                "wo_code": wo_code,
            }
        )

    exceeded = [f for f in facts if (f.get("limit") or {}).get("exceeded")]
    if exceeded and top.get("cause"):
        out.append(
            {
                "text": (
                    f"Síntoma actual coincide con histórico {wo_code}; verificar si la causa "
                    f"«{top.get('cause')}» fue resuelta definitivamente"
                ),
                "severity": "warn",
                "rule": "reading_vs_wo",
                "kind": "eam_history",
                "wo_code": wo_code,
            }
        )
    return out


def detect_doc_conflicts(
    asset_id: str,
    facts: list[dict[str, Any]],
    hits: list[SearchResult],
    *,
    rules: dict[str, Any],
) -> list[dict[str, Any]]:
    if not rules.get("rules", {}).get("doc_version_conflict", True):
        return []
    out: list[dict[str, Any]] = []
    fact_tags = {(f.get("sensor") or {}).get("tag", "").upper() for f in facts}

    for conflict in get_doc_conflicts(asset_id):
        tag = (conflict.get("tag") or "").upper()
        if tag and tag not in fact_tags and not any(tag in (h.content or "").upper() for h in hits):
            continue
        out.append(
            {
                "text": f"{tag or 'Documento'}: conflicto de versiones — {conflict.get('doc_a')} vs {conflict.get('doc_b')}",
                "severity": conflict.get("severity") or "warn",
                "rule": "doc_version_conflict",
                "kind": "c2_contradiction",
                "tag": tag,
            }
        )

    version_labels = {h.version_label for h in hits if h.version_label}
    if len(version_labels) > 1:
        out.append(
            {
                "text": f"Evidencia recuperada mezcla versiones documentales: {', '.join(sorted(version_labels)[:4])}",
                "severity": "info",
                "rule": "doc_version_conflict",
                "kind": "c2_contradiction",
            }
        )
    return out


def build_discrepancy_banner(discrepancies: list[dict[str, Any]]) -> dict[str, Any]:
    if not discrepancies:
        return {"visible": False, "count": 0, "message": "", "severity": "info"}
    warn_count = sum(1 for d in discrepancies if d.get("severity") == "warn")
    severity = "warn" if warn_count else "info"
    count = len(discrepancies)
    return {
        "visible": True,
        "count": count,
        "message": f"{count} discrepancia{'s' if count != 1 else ''} detectada{'s' if count != 1 else ''} — no bloquea el análisis",
        "severity": severity,
    }


def merge_discrepancies(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        for raw in group:
            row = _validate_discrepancy(raw)
            if not row or row["text"].lower() in seen:
                continue
            seen.add(row["text"].lower())
            merged.append(row)
    merged.sort(key=lambda d: (0 if d["severity"] == "warn" else 1, d["text"]))
    return merged


def process_discrepancies(
    raw_discrepancies: list[dict[str, Any]],
    *,
    asset_id: str,
    symptom: str,
    facts: list[dict[str, Any]],
    hits: list[SearchResult],
    rules: dict[str, Any] | None = None,
    today: date | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pipeline M6: reglas + LLM + banner."""
    cfg = rules if rules is not None else load_discrepancy_rules()
    llm_rows = [_validate_discrepancy(d) for d in raw_discrepancies]
    llm_rows = [r for r in llm_rows if r]

    detected = merge_discrepancies(
        detect_calibration_discrepancies(asset_id, rules=cfg, today=today),
        detect_wo_discrepancies(asset_id, symptom, facts, rules=cfg),
        detect_doc_conflicts(asset_id, facts, hits, rules=cfg),
        llm_rows,
    )
    banner = build_discrepancy_banner(detected)
    return detected, banner
