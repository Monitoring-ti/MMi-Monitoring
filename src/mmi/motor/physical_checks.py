"""Verificación física: normalización, priorización y fallback."""

from __future__ import annotations

from typing import Any

_VALID_PRIORITIES = {"urgent", "normal", "routine"}


def validate_physical_check(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    text = (raw.get("text") or "").strip()
    if not text:
        return None
    priority = (raw.get("priority") or "normal").strip().lower()
    if priority == "routine":
        priority = "normal"
    if priority not in _VALID_PRIORITIES:
        priority = "normal"
    return {"text": text, "priority": priority, "checked": False}


def _has_exceeded_alarms(facts: list[dict[str, Any]]) -> bool:
    return any((f.get("limit") or {}).get("exceeded") is True for f in facts)


def _upgrade_priority(priority: str, *, asset: dict[str, Any], has_alarms: bool) -> str:
    if priority == "urgent":
        return "urgent"
    criticality = (asset.get("criticality") or "").upper()
    if has_alarms and criticality in {"A", "B"}:
        return "urgent"
    return priority


def prioritize_checks(
    checks: list[dict[str, Any]],
    *,
    asset: dict[str, Any],
    facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    has_alarms = _has_exceeded_alarms(facts)
    out: list[dict[str, Any]] = []
    for check in checks:
        row = dict(check)
        row["priority"] = _upgrade_priority(row.get("priority") or "normal", asset=asset, has_alarms=has_alarms)
        row.setdefault("checked", False)
        out.append(row)
    out.sort(key=lambda c: (0 if c["priority"] == "urgent" else 1, c["text"]))
    return out


def generate_fallback_checks(
    facts: list[dict[str, Any]],
    *,
    asset: dict[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    tags = [(f.get("sensor") or {}).get("tag") for f in facts if (f.get("sensor") or {}).get("tag")]
    if any((f.get("limit") or {}).get("exceeded") for f in facts if "TE-" in str((f.get("sensor") or {}).get("tag", ""))):
        checks.append(
            {
                "text": "Medir temperatura de salida y comparar con límite documentado en ATM/FMECA",
                "priority": "urgent",
            }
        )
    if any((f.get("limit") or {}).get("exceeded") for f in facts if "FT-" in str((f.get("sensor") or {}).get("tag", ""))):
        checks.append(
            {
                "text": "Verificar posición y estado de válvula de control / caudalímetro",
                "priority": "urgent",
            }
        )
    if any((f.get("limit") or {}).get("exceeded") for f in facts if "VE-" in str((f.get("sensor") or {}).get("tag", ""))):
        checks.append(
            {
                "text": "Inspeccionar bomba: vibración, sellos y cavitación",
                "priority": "urgent",
            }
        )
    if tags:
        checks.append(
            {
                "text": f"Confirmar calibración vigente de instrumentación ({', '.join(tags[:3])})",
                "priority": "normal",
            }
        )
    checks.append(
        {
            "text": f"Registrar hallazgos en CMMS para activo {asset.get('id') or asset.get('name')}",
            "priority": "normal",
        }
    )
    return [c for c in (validate_physical_check(x) for x in checks) if c]


def load_fixture_checks(asset_id: str) -> list[dict[str, Any]]:
    from mmi.motor.page import load_motor_fixture

    demo = load_motor_fixture().get("demo_analysis") or {}
    if (demo.get("asset_id") or "").upper() != (asset_id or "").upper():
        return []
    return list(demo.get("physical_checks") or [])


def process_physical_checks(
    raw_checks: list[dict[str, Any]],
    *,
    asset: dict[str, Any],
    facts: list[dict[str, Any]],
    min_count: int = 3,
) -> list[dict[str, Any]]:
    """Pipeline M5: validar, priorizar y completar checklist."""
    valid: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_checks:
        row = validate_physical_check(raw)
        if not row or row["text"].lower() in seen:
            continue
        seen.add(row["text"].lower())
        valid.append(row)

    if len(valid) < min_count:
        for raw in load_fixture_checks(asset.get("id") or ""):
            row = validate_physical_check(raw)
            if row and row["text"].lower() not in seen:
                valid.append(row)
                seen.add(row["text"].lower())

    if len(valid) < min_count:
        for row in generate_fallback_checks(facts, asset=asset):
            if row["text"].lower() not in seen:
                valid.append(row)
                seen.add(row["text"].lower())

    return prioritize_checks(valid, asset=asset, facts=facts)
