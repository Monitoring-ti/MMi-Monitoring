"""Hipótesis del sistema: validación, ranking y vínculo a hechos verificados."""

from __future__ import annotations

from typing import Any

INFERENCE_DISCLAIMER = "Inferencia IA — requiere criterio del especialista."

_FORBIDDEN_HYP_KINDS = {"document", "measurement", "fact", "verified"}


def _clamp_pct(value: Any) -> int:
    try:
        pct = int(round(float(value)))
    except (TypeError, ValueError):
        return 50
    return max(0, min(pct, 100))


def _normalize_indices(raw: Any, fact_count: int) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for item in raw:
        try:
            idx = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= idx <= fact_count and idx not in out:
            out.append(idx)
    return out


def _link_supported_facts(indices: list[int], facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    linked: list[dict[str, Any]] = []
    for idx in indices:
        fact = facts[idx - 1]
        sensor = fact.get("sensor") or {}
        linked.append(
            {
                "index": idx,
                "text": (fact.get("text") or "")[:160],
                "tag": sensor.get("tag"),
                "kind": fact.get("kind") or "document",
            }
        )
    return linked


def validate_hypothesis(raw: dict[str, Any], *, fact_count: int) -> dict[str, Any] | None:
    """Valida una hipótesis; rechaza si parece un hecho verificado."""
    if not isinstance(raw, dict):
        return None
    kind = (raw.get("kind") or "inference").strip().lower()
    if kind in _FORBIDDEN_HYP_KINDS:
        return None

    title = (raw.get("title") or "").strip()
    rationale = (raw.get("rationale") or "").strip()
    if not title or not rationale:
        return None

    indices = _normalize_indices(raw.get("supported_fact_indices"), fact_count)
    if fact_count > 0 and not indices:
        return None

    return {
        "id": (raw.get("id") or "H?").strip(),
        "title": title,
        "rationale": rationale,
        "confidence_pct": _clamp_pct(raw.get("confidence_pct")),
        "supported_fact_indices": indices,
        "kind": "inference",
        "inference_disclaimer": INFERENCE_DISCLAIMER,
    }


def normalize_hypotheses(
    hypotheses: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    *,
    min_count: int = 2,
    max_count: int = 3,
) -> list[dict[str, Any]]:
    """Valida, rankea y enriquece hipótesis con hechos soportados."""
    fact_count = len(facts)
    valid: list[dict[str, Any]] = []
    for raw in hypotheses:
        row = validate_hypothesis(raw, fact_count=fact_count)
        if row:
            valid.append(row)

    valid.sort(key=lambda h: h["confidence_pct"], reverse=True)
    valid = valid[:max_count]

    for i, hyp in enumerate(valid, 1):
        hyp["id"] = f"H{i}"
        hyp["supported_facts"] = _link_supported_facts(hyp["supported_fact_indices"], facts)

    if fact_count > 0 and len(valid) < min_count:
        fallback = generate_fallback_hypotheses(facts)
        seen_titles = {h["title"].lower() for h in valid}
        for hyp in fallback:
            if hyp["title"].lower() in seen_titles:
                continue
            valid.append(hyp)
            seen_titles.add(hyp["title"].lower())
            if len(valid) >= min_count:
                break
        valid.sort(key=lambda h: h["confidence_pct"], reverse=True)
        for i, hyp in enumerate(valid[:max_count], 1):
            hyp["id"] = f"H{i}"
            hyp["supported_facts"] = _link_supported_facts(hyp["supported_fact_indices"], facts)

    return valid[:max_count]


def _fact_index_by_tag(facts: list[dict[str, Any]], tag: str) -> int | None:
    tag_u = tag.upper()
    for i, fact in enumerate(facts, 1):
        sensor = fact.get("sensor") or {}
        if (sensor.get("tag") or "").upper() == tag_u:
            return i
    return None


def generate_fallback_hypotheses(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Genera hipótesis deterministas a partir de hechos de medición (sin LLM)."""
    if not facts:
        return []

    te_idx = _fact_index_by_tag(facts, "TE-401A")
    ft_idx = _fact_index_by_tag(facts, "FT-405")
    ve_idx = _fact_index_by_tag(facts, "VE-402X")

    te_exceeded = _is_exceeded(facts, te_idx)
    ft_exceeded = _is_exceeded(facts, ft_idx)
    ve_exceeded = _is_exceeded(facts, ve_idx)

    candidates: list[dict[str, Any]] = []

    if te_exceeded and ft_exceeded:
        candidates.append(
            {
                "title": "Obstrucción parcial en intercambiador o válvula de control",
                "rationale": "Temperatura de salida elevada con caudal por debajo del nominal.",
                "confidence_pct": 88,
                "supported_fact_indices": [i for i in (te_idx, ft_idx) if i],
            }
        )

    if ft_exceeded and ve_exceeded:
        candidates.append(
            {
                "title": "Degradación de sellos o cavitación en bomba de circulación",
                "rationale": "Vibración elevada en 1× RPM con caudal reducido.",
                "confidence_pct": 65,
                "supported_fact_indices": [i for i in (ft_idx, ve_idx) if i],
            }
        )

    if te_exceeded and not candidates:
        candidates.append(
            {
                "title": "Restricción térmica en intercambiador o control de temperatura",
                "rationale": "Lectura de temperatura por encima del límite documentado.",
                "confidence_pct": 72,
                "supported_fact_indices": [te_idx] if te_idx else [1],
            }
        )

    if not candidates:
        candidates.append(
            {
                "title": "Desviación operativa sin patrón único identificado",
                "rationale": "Los sensores muestran variación respecto a límites o nominal documentado.",
                "confidence_pct": 55,
                "supported_fact_indices": list(range(1, min(len(facts), 2) + 1)),
            }
        )

    out: list[dict[str, Any]] = []
    for raw in candidates:
        row = validate_hypothesis(raw, fact_count=len(facts))
        if row:
            out.append(row)
    return out


def _is_exceeded(facts: list[dict[str, Any]], index: int | None) -> bool:
    if not index or index < 1 or index > len(facts):
        return False
    return (facts[index - 1].get("limit") or {}).get("exceeded") is True


def load_fixture_hypotheses(asset_id: str) -> list[dict[str, Any]]:
    from mmi.motor.page import load_motor_fixture

    demo = load_motor_fixture().get("demo_analysis") or {}
    if (demo.get("asset_id") or "").upper() == (asset_id or "").upper():
        return list(demo.get("hypotheses") or [])
    return []


def process_hypotheses(
    raw_hypotheses: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    *,
    asset_id: str = "",
    min_count: int = 2,
) -> list[dict[str, Any]]:
    """Pipeline M4: validar LLM, completar con fallback y enriquecer."""
    normalized = normalize_hypotheses(raw_hypotheses, facts, min_count=min_count)
    if len(normalized) >= min_count:
        return normalized

    for hyp in load_fixture_hypotheses(asset_id):
        normalized = normalize_hypotheses(normalized + [hyp], facts, min_count=min_count)
        if len(normalized) >= min_count:
            return normalized

    return normalize_hypotheses(normalized + generate_fallback_hypotheses(facts), facts, min_count=min_count)
