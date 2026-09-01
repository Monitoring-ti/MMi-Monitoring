"""Análisis Motor MMI: recuperación + LLM estructurado."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from mmi.catalog.assets import load_assets
from mmi.llm.openrouter import chat_completion
from mmi.motor.hypotheses import process_hypotheses
from mmi.motor.discrepancies import process_discrepancies
from mmi.motor.eam_history import build_eam_history_payload
from mmi.motor.page import load_motor_fixture
from mmi.motor.physical_checks import process_physical_checks
from mmi.motor.sensors import get_sensor_readings
from mmi.motor.verified_facts import (
    build_measurement_facts,
    compute_aggregate_confidence,
    merge_verified_facts,
)
from mmi.search.engine import HybridSearchEngine, SearchResult

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

SYSTEM_PROMPT = """Eres un especialista de mantenibilidad industrial (ODS1, NCC-30).
Analiza el síntoma del activo usando SOLO las evidencias numeradas [1], [2], etc.

Responde ÚNICAMENTE con un objeto JSON válido (sin markdown) con esta estructura:
{
  "diagnosis": {
    "summary": "2-4 oraciones",
    "confidence_label": "alta|media|baja",
    "confidence_pct": 0-100
  },
  "verified_facts": [
    {
      "text": "hecho verificable con datos o cita documental",
      "kind": "document|measurement",
      "citation_index": 1
    }
  ],
  "hypotheses": [
    {
      "id": "H1",
      "title": "título breve",
      "rationale": "justificación",
      "confidence_pct": 0-100,
      "supported_fact_indices": [1],
      "kind": "inference"
    }
  ],
  "physical_checks": [
    {"text": "acción verificable en terreno", "priority": "urgent|normal"}
  ],
  "discrepancies": [
    {"text": "conflicto o dato faltante", "severity": "warn|info"}
  ]
}

Reglas:
- verified_facts: solo afirmaciones respaldadas por evidencias [n]; citation_index obligatorio.
- hypotheses: inferencias (kind=inference); siempre ≥2 si hay hechos verificados; confidence_pct por hipótesis; supported_fact_indices obligatorio.
- physical_checks: acciones concretas para el técnico en planta.
- discrepancies: vacío [] si no hay conflicto detectable.
- No inventes sensores, valores ni documentos fuera de las evidencias.
- Español técnico, conciso."""


@dataclass
class MotorAnalysisResult:
    asset: dict[str, Any]
    symptom: str
    window: str
    diagnosis: dict[str, Any]
    verified_facts: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    physical_checks: list[dict[str, Any]]
    discrepancies: list[dict[str, Any]]
    sources_preview: list[str]
    references: list[dict[str, Any]]
    hits: list[SearchResult]
    model: str
    discrepancy_banner: dict[str, Any] = field(
        default_factory=lambda: {"visible": False, "count": 0, "message": "", "severity": "info"}
    )
    eam_history: dict[str, Any] = field(default_factory=dict)


def resolve_asset(asset_id: str, *, tenant_slug: str = "monitoring") -> dict[str, Any]:
    tag = (asset_id or "").strip().upper()
    if tag:
        try:
            catalog = load_assets(tenant_slug=tenant_slug)
            row = catalog.get(tag)
            if row:
                return {
                    "id": row.asset_tag,
                    "name": row.asset_tag,
                    "modulo": row.modulo or "",
                    "criticality": "B",
                }
        except RuntimeError:
            pass
    for asset in load_motor_fixture().get("assets") or []:
        if asset.get("id") == asset_id:
            return dict(asset)
    return {"id": asset_id, "name": asset_id, "modulo": "", "criticality": "B"}


def build_search_query(symptom: str, asset: dict[str, Any]) -> str:
    parts = [symptom.strip(), f"activo {asset.get('name') or asset.get('id')}"]
    if asset.get("modulo"):
        parts.append(str(asset["modulo"]))
    return " ".join(p for p in parts if p)


def _format_sensor_block(readings: list) -> str:
    if not readings:
        return ""
    lines = ["Lecturas de sensores (PI/SCADA, ventana activa):"]
    for r in readings:
        line = f"- {r.tag}: {r.value:g} {r.unit}"
        if r.nominal is not None:
            line += f" (nominal {r.nominal:g})"
        line += f" @ {r.timestamp.isoformat()}"
        lines.append(line)
    return "\n".join(lines) + "\n\n"


def _format_evidence(hits: list[SearchResult]) -> str:
    blocks: list[str] = []
    for i, h in enumerate(hits, 1):
        cite = h.citation or h.titulo or f"Fuente {i}"
        blocks.append(f"[{i}] {cite}\n{h.content[:3000]}")
    return "\n\n".join(blocks)


def _strip_json_fences(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text.strip()).strip()


def parse_motor_response(raw: str) -> dict[str, Any]:
    text = _strip_json_fences(raw)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("respuesta motor no es objeto JSON")
    for key in ("diagnosis", "verified_facts", "hypotheses", "physical_checks", "discrepancies"):
        data.setdefault(key, [] if key != "diagnosis" else {})
    return data


def _attach_fact_sources(facts: list[dict], hits: list[SearchResult]) -> list[dict]:
    out: list[dict] = []
    for fact in facts:
        row = dict(fact)
        idx = int(row.get("citation_index") or 0)
        if 1 <= idx <= len(hits):
            hit = hits[idx - 1]
            row["source"] = {
                "type": "document",
                "citation": hit.citation or hit.titulo or f"Evidencia {idx}",
                "document_id": hit.document_id,
                "titulo": hit.titulo,
            }
        else:
            row["source"] = {"type": "document", "citation": ""}
        out.append(row)
    return out


def _build_references(hits: list[SearchResult]) -> list[dict]:
    refs: list[dict] = []
    for i, h in enumerate(hits, 1):
        refs.append(
            {
                "index": i,
                "citation": h.citation,
                "titulo": h.titulo,
                "tipo": h.tipo,
                "version_label": h.version_label,
                "section_path": h.section_path,
                "page_start": h.page_start,
                "page_end": h.page_end,
                "score": round(h.score, 4),
                "snippet": h.content[:280].strip(),
            }
        )
    return refs


def _build_m6_context(
    asset_id: str,
    symptom: str,
    facts: list[dict[str, Any]],
    hits: list[SearchResult],
    raw_discrepancies: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    discrepancies, banner = process_discrepancies(
        raw_discrepancies,
        asset_id=asset_id,
        symptom=symptom,
        facts=facts,
        hits=hits,
    )
    eam_history = build_eam_history_payload(asset_id, symptom)
    return discrepancies, banner, eam_history


def analyze_motor(
    asset_id: str,
    symptom: str,
    engine: HybridSearchEngine,
    *,
    window: str = "24h",
    limit: int = 8,
    model: str | None = None,
    tenant_slug: str = "monitoring",
) -> MotorAnalysisResult:
    import os

    symptom = (symptom or "").strip()
    if not symptom:
        raise ValueError("symptom es obligatorio")
    if not (asset_id or "").strip():
        raise ValueError("asset_id es obligatorio")

    asset = resolve_asset(asset_id, tenant_slug=tenant_slug)
    query = build_search_query(symptom, asset)
    hits = engine.search(query, limit=limit)
    sensor_readings = get_sensor_readings(asset.get("id") or asset_id, window=window)
    structured_facts = build_measurement_facts(sensor_readings, hits) if sensor_readings else []

    if not hits and not structured_facts:
        used_model = model or os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        checks = process_physical_checks(
            [{"text": "Verificar código de activo en catálogo EAM y ampliar síntoma con equipo/tag", "priority": "normal"}],
            asset=asset,
            facts=[],
        )
        disc, banner, eam = _build_m6_context(asset.get("id") or asset_id, symptom, [], [], [])
        return MotorAnalysisResult(
            asset=asset,
            symptom=symptom,
            window=window,
            diagnosis={
                "summary": "No se encontró evidencia documental en el corpus para este activo y síntoma.",
                "confidence_label": "baja",
                "confidence_pct": 0,
            },
            verified_facts=[],
            hypotheses=[],
            physical_checks=checks,
            discrepancies=disc,
            discrepancy_banner=banner,
            eam_history=eam,
            sources_preview=[],
            references=[],
            hits=[],
            model=used_model,
        )

    if not hits and structured_facts:
        diagnosis = compute_aggregate_confidence(
            structured_facts,
            {
                "summary": (
                    "Lecturas de sensores fuera de rango documentado; sin evidencia textual adicional en corpus."
                ),
                "confidence_label": "media",
                "confidence_pct": 70,
            },
        )
        used_model = model or os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        hypotheses = process_hypotheses([], structured_facts, asset_id=asset.get("id") or asset_id)
        checks = process_physical_checks(
            [{"text": f"Verificar instrumentación {structured_facts[0].get('sensor', {}).get('tag', '')}", "priority": "urgent"}],
            asset=asset,
            facts=structured_facts,
        )
        disc, banner, eam = _build_m6_context(
            asset.get("id") or asset_id,
            symptom,
            structured_facts,
            [],
            [],
        )
        return MotorAnalysisResult(
            asset=asset,
            symptom=symptom,
            window=window,
            diagnosis=diagnosis,
            verified_facts=structured_facts,
            hypotheses=hypotheses,
            physical_checks=checks,
            discrepancies=disc,
            discrepancy_banner=banner,
            eam_history=eam,
            sources_preview=[],
            references=[],
            hits=[],
            model=used_model,
        )

    evidence = _format_evidence(hits)
    sensor_block = _format_sensor_block(sensor_readings)
    user_prompt = f"""Activo: {asset.get('name')} ({asset.get('id')})
Módulo: {asset.get('modulo') or '—'}
Ventana temporal: {window}

Síntoma reportado:
{symptom}

{sensor_block}Evidencias del corpus:
{evidence}

Genera el JSON de análisis motor. Los hechos de medición con sensor ya están verificados; no los repitas salvo contexto adicional."""

    used_model = model or os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    raw = chat_completion(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model=used_model,
        max_tokens=1600,
    )
    if isinstance(raw, tuple):
        raw = raw[0]

    parsed = parse_motor_response(str(raw))
    llm_facts = _attach_fact_sources(parsed.get("verified_facts") or [], hits)
    facts = merge_verified_facts(structured_facts, llm_facts)
    diagnosis = compute_aggregate_confidence(facts, parsed.get("diagnosis") or {})
    hypotheses = process_hypotheses(
        parsed.get("hypotheses") or [],
        facts,
        asset_id=asset.get("id") or asset_id,
    )
    checks = process_physical_checks(
        parsed.get("physical_checks") or [],
        asset=asset,
        facts=facts,
    )
    refs = _build_references(hits)
    sources_preview = [r["titulo"] or r["citation"] or "" for r in refs[:6] if r.get("titulo") or r.get("citation")]

    disc, banner, eam = _build_m6_context(
        asset.get("id") or asset_id,
        symptom,
        facts,
        hits,
        parsed.get("discrepancies") or [],
    )

    return MotorAnalysisResult(
        asset=asset,
        symptom=symptom,
        window=window,
        diagnosis=diagnosis,
        verified_facts=facts,
        hypotheses=hypotheses,
        physical_checks=checks,
        discrepancies=disc,
        discrepancy_banner=banner,
        eam_history=eam,
        sources_preview=sources_preview,
        references=refs,
        hits=hits,
        model=used_model,
    )
