"""Hechos verificados: datos de sensor + límites OEM documentales."""

from __future__ import annotations

from typing import Any

from mmi.motor.oem_limits import OemLimit, extract_limits_from_hits
from mmi.motor.sensors import SensorReading
from mmi.search.engine import SearchResult

_KIND_TO_LIMIT = {
    "max_temp": "max",
    "max_vibration": "max",
    "min_flow": "min",
    "nominal_flow": "nominal",
    "generic_limit": "max",
}


def _pick_limit_for_reading(
    reading: SensorReading,
    limits: list[tuple[int, OemLimit]],
) -> tuple[int | None, OemLimit | None]:
    tag = reading.tag.upper()
    unit = reading.unit.replace(" ", "").lower()
    candidates: list[tuple[int, OemLimit, int]] = []

    for cite_idx, lim in limits:
        lim_tag = (lim.tag or "").upper()
        lim_unit = lim.unit.replace(" ", "").lower()
        if lim_tag and lim_tag != tag:
            continue
        if lim_unit and unit and lim_unit != unit.lower().replace("°", "°"):
            if not (lim_unit in unit.lower() or unit.lower() in lim_unit):
                continue
        score = 0
        if lim_tag == tag:
            score += 3
        if reading.unit and lim.unit and reading.unit.lower() in lim.unit.lower():
            score += 2
        if lim.kind == "max_temp" and "°" in reading.unit:
            score += 1
        if lim.kind in {"nominal_flow", "min_flow"} and "l/min" in unit:
            score += 1
        if lim.kind == "max_vibration" and "mm" in unit:
            score += 1
        candidates.append((cite_idx, lim, score))

    if not candidates:
        return None, None
    candidates.sort(key=lambda x: x[2], reverse=True)
    best = candidates[0]
    return best[0], best[1]


def _limit_kind(lim: OemLimit) -> str:
    return _KIND_TO_LIMIT.get(lim.kind, "max")


def _is_exceeded(reading: SensorReading, lim: OemLimit) -> bool | None:
    kind = _limit_kind(lim)
    if kind == "max":
        return reading.value > lim.value
    if kind == "min":
        return reading.value < lim.value
    if kind == "nominal" and reading.nominal is not None:
        return abs(reading.value - reading.nominal) > abs(reading.nominal * 0.15)
    if kind == "nominal":
        return abs(reading.value - lim.value) > abs(lim.value * 0.15)
    return None


def _format_fact_text(
    reading: SensorReading,
    lim: OemLimit | None,
    *,
    exceeded: bool | None,
) -> str:
    base = f"{reading.description} {reading.tag}: {reading.value:g} {reading.unit}"
    if reading.nominal is not None:
        base += f" (nominal {reading.nominal:g} {reading.unit})"
    elif lim is not None:
        label = "límite" if _limit_kind(lim) == "max" else lim.kind.replace("_", " ")
        base += f" ({label} documentado {lim.value:g} {lim.unit})"
    if exceeded is True:
        base += " — FUERA DE LÍMITE"
    elif exceeded is False:
        base += " — dentro de límite"
    return base


def _fact_confidence(
    *,
    has_doc: bool,
    exceeded: bool | None,
    has_nominal: bool,
) -> dict[str, Any]:
    pct = 55
    if has_doc:
        pct += 25
    if exceeded is not None:
        pct += 10
    if has_nominal:
        pct += 5
    pct = min(pct, 98)
    if pct >= 85:
        label = "alta"
    elif pct >= 60:
        label = "media"
    else:
        label = "baja"
    return {"level": label, "pct": pct}


def build_measurement_facts(
    readings: list[SensorReading],
    hits: list[SearchResult],
) -> list[dict[str, Any]]:
    """Construye hechos verificados estructurados (dato + límite + cita)."""
    if not readings:
        return []

    tags = [r.tag for r in readings]
    limits = extract_limits_from_hits(hits, tags=tags)
    facts: list[dict[str, Any]] = []

    for i, reading in enumerate(readings, 1):
        cite_idx, lim = _pick_limit_for_reading(reading, limits)
        exceeded = _is_exceeded(reading, lim) if lim else None
        if lim is None and reading.nominal is not None:
            pct_diff = abs(reading.value - reading.nominal) / max(reading.nominal, 1)
            exceeded = pct_diff > 0.15

        source: dict[str, Any] = {"type": "sensor", "citation": f"PI/SCADA · {reading.tag}"}
        if cite_idx and 1 <= cite_idx <= len(hits):
            hit = hits[cite_idx - 1]
            source = {
                "type": "document",
                "citation": hit.citation or hit.titulo or f"Evidencia {cite_idx}",
                "document_id": hit.document_id,
                "titulo": hit.titulo,
            }

        limit_block: dict[str, Any] | None = None
        if lim is not None:
            limit_block = {
                "value": lim.value,
                "unit": lim.unit,
                "kind": _limit_kind(lim),
                "exceeded": exceeded,
            }
        elif reading.nominal is not None:
            limit_block = {
                "value": reading.nominal,
                "unit": reading.unit,
                "kind": "nominal",
                "exceeded": exceeded,
            }

        facts.append(
            {
                "text": _format_fact_text(reading, lim, exceeded=exceeded),
                "kind": "measurement",
                "citation_index": cite_idx or i,
                "sensor": reading.to_dict(),
                "limit": limit_block,
                "source": source,
                "confidence": _fact_confidence(
                    has_doc=bool(cite_idx and lim),
                    exceeded=exceeded,
                    has_nominal=reading.nominal is not None,
                ),
            }
        )
    return facts


def merge_verified_facts(
    structured: list[dict[str, Any]],
    llm_facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prioriza hechos estructurados (sensor+doc); añade hechos LLM no duplicados."""
    if not structured:
        return llm_facts
    seen_tags = {(f.get("sensor") or {}).get("tag", "").upper() for f in structured if f.get("sensor")}
    merged = list(structured)
    for fact in llm_facts:
        text = (fact.get("text") or "").upper()
        if any(tag and tag in text for tag in seen_tags if tag):
            continue
        merged.append(fact)
    return merged


def compute_aggregate_confidence(
    facts: list[dict[str, Any]],
    diagnosis: dict[str, Any],
) -> dict[str, Any]:
    """Badge de confianza agregada según nº fuentes y acuerdo dato-documento."""
    if not facts:
        return dict(diagnosis)

    pcts = [int((f.get("confidence") or {}).get("pct") or 0) for f in facts]
    with_doc = sum(1 for f in facts if (f.get("source") or {}).get("type") == "document")
    exceeded = sum(1 for f in facts if (f.get("limit") or {}).get("exceeded") is True)

    avg = sum(pcts) / len(pcts) if pcts else int(diagnosis.get("confidence_pct") or 0)
    bonus = min(with_doc * 3, 9) + (5 if exceeded and with_doc else 0)
    pct = min(int(round(avg + bonus)), 98)

    if pct >= 85:
        label = "alta"
    elif pct >= 60:
        label = "media"
    else:
        label = "baja"

    out = dict(diagnosis)
    out["confidence_pct"] = pct
    out["confidence_label"] = label
    out["verified_fact_count"] = len(facts)
    out["document_backed_count"] = with_doc
    return out
