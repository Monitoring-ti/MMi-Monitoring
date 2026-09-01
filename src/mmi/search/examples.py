"""Ejemplos de búsqueda anclados al corpus ODS1 indexado."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

Example = dict[str, str]

_CATEGORIES: tuple[dict[str, Any], ...] = (
    {
        "icon": "NCC",
        "title": "Normas y guías NCC30",
        "tag": "NCC-030 · GUIGS Rev 6 · PROGS-0001",
        "note": "Norma, guía de mantenibilidad y procedimiento de estudios/proyectos.",
        "examples": (
            {"label": "NCC-030 criticidad", "query": "NCC-030 requisitos criticidad mantenibilidad confiabilidad"},
            {"label": "GUIGS Rev 6 alcance", "query": "SGP-07MYC-GUIGS-00001 Rev 6 alcance mantenibilidad confiabilidad proyectos"},
            {"label": "PROGS-0001 etapas", "query": "SGPD-07MYC-PROGS-0001 procedimiento mantenibilidad estudios proyectos pasos etapas"},
        ),
    },
    {
        "icon": "MX",
        "title": "Matrices de planes ODS21",
        "tag": "MRI · MSO · SPCI · tablas",
        "note": "La mayor parte del índice: matrices de mantenimiento, operación e inspección.",
        "examples": (
            {"label": "Matriz MRI", "query": "matriz planes MRI mantenimiento preventivo ODS21", "action": "search"},
            {"label": "Matriz MSO", "query": "matriz planes MSO operación mantenimiento sistema", "action": "search"},
            {"label": "Matriz SPCI", "query": "matriz planes SPCI inspección criticidad equipos", "action": "search"},
        ),
    },
    {
        "icon": "F",
        "title": "FMECA y modos de falla",
        "tag": "Anexos FMECA · talleres",
        "note": "Análisis de modos, efectos y criticidad del sistema de enfriamiento ODS1.",
        "examples": (
            {"label": "FMECA enfriamiento", "query": "FMECA modos falla efectos criticidad sistema enfriamiento torre DCH"},
            {"label": "Anexo FMECA mecánico", "query": "ANEXO A FMECA MEC REEMP SIST ENFR CTS DCH modos falla", "action": "search"},
            {"label": "Taller FMECA", "query": "taller FMECA monitoring capacitación NCC30", "action": "search"},
        ),
    },
    {
        "icon": "RCM",
        "title": "RCM y pautas de mantenimiento",
        "tag": "FRMGS-0036 · estimaciones",
        "note": "Plantillas RCM, pautas y estimaciones de mantenimiento del proyecto.",
        "examples": (
            {"label": "Plantilla RCM", "query": "SGPD-07MYC-FRMGS-0036 RCM tareas mantenimiento recomendadas"},
            {"label": "Pautas ODS1", "query": "ODS1 estim RCM pautas mantenimiento preventivo", "action": "search"},
            {"label": "Tareas RCM", "query": "análisis RCM tareas inspección reemplazo componentes", "action": "search"},
        ),
    },
    {
        "icon": "❄",
        "title": "Sistema de enfriamiento ODS1",
        "tag": "Torre DCH · ATM · operación",
        "note": "Filosofía de operación, ATM y documentación del sistema de torre de enfriamiento.",
        "examples": (
            {"label": "ATM enfriamiento", "query": "ANEXO A ATM sistema enfriamiento torre DCH operación", "action": "search"},
            {"label": "Filosofía operación", "query": "filosofía operación torre enfriamiento PTS DCH"},
            {"label": "Taller M&C STMA", "query": "taller mantenibilidad confiabilidad sistema enfriamiento ODS1", "action": "search"},
        ),
    },
    {
        "icon": "✓",
        "title": "Checklist y criterios",
        "tag": "Anexo C · IFC 078",
        "note": "Listas de verificación de diseño y clasificación de equipos.",
        "examples": (
            {"label": "Anexo C GUIGS", "query": "Anexo C checklist accesibilidad cumplimiento mantenibilidad GUIGS"},
            {"label": "IFC 078 criticidad", "query": "IFC 078 clasificación equipos criticidad infraestructura"},
            {"label": "Acceso mantenimiento", "query": "criterios acceso mantenimiento equipos pesados checklist diseño"},
        ),
    },
    {
        "icon": "OEM",
        "title": "Manuales y equipos",
        "tag": "Sala eléctrica · interconexión",
        "note": "Manuales OEM, diagramas e informes técnicos de equipos del proyecto.",
        "examples": (
            {"label": "Sala eléctrica", "query": "4400285992 equipos sala eléctrica especificaciones mantenimiento", "action": "search"},
            {"label": "Interconexión EL", "query": "interconexión fuerza control cableado mantenimiento", "action": "search"},
            {"label": "Informes M&C", "query": "informe observaciones mantenibilidad confiabilidad INFMC", "action": "search"},
        ),
    },
    {
        "icon": "PPT",
        "title": "Capacitación y talleres",
        "tag": "Presentaciones · formación",
        "note": "Material de capacitación NCC30, talleres finales y presentaciones de operación.",
        "examples": (
            {"label": "Filosofía operación", "query": "presentación filosofía operación torre enfriamiento Rev 2", "action": "search"},
            {"label": "Taller NCC30 ODS21", "query": "taller final NCC30 ODS21 mantenibilidad confiabilidad", "action": "search"},
            {"label": "Capacitación FMECA", "query": "FMECA MONITORING capacitación modos falla presentación", "action": "search"},
        ),
    },
)

_TIPS: tuple[dict[str, Any], ...] = (
    {
        "icon": "?",
        "title": "Formular la pregunta",
        "tag": "Preguntas completas",
        "note": "Incluye qué necesitas (definición, criterio, paso) y contexto (fase, equipo, anexo).",
        "examples": (
            {"label": "Definición M&C", "query": "¿Qué es la mantenibilidad y cómo se evalúa según GUIGS Rev 6?"},
            {"label": "Alcance análisis", "query": "¿Cuál es el alcance del análisis de mantenibilidad en proyectos de inversión?"},
        ),
    },
    {
        "icon": "⇄",
        "title": "Buscar vs Responder",
        "tag": "Modos de consulta",
        "note": "Buscar devuelve fragmentos; Responder redacta con citas [1][2]. Explora y luego refina.",
        "examples": (
            {"label": "Buscar fragmentos", "query": "checklist accesibilidad mantenimiento", "action": "search"},
            {"label": "Responder con citas", "query": "¿Cuáles son los criterios de criticidad según NCC-030?"},
        ),
    },
)


def load_corpus_stats(out_dir: Path | None = None) -> dict[str, Any]:
    """Lee resumen del corpus desde out/analysis-status.json si existe."""
    root = out_dir or Path("out")
    path = root / "analysis-status.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    idx = data.get("index_summary") or {}
    token = data.get("token_summary") or {}
    return {
        "docs": idx.get("indexados") or token.get("index_docs") or 0,
        "chunks": idx.get("chunks") or token.get("index_chunks") or 0,
        "tokens_fmt": token.get("index_tokens_fmt") or "",
        "lote": data.get("lote") or "",
    }


def _render_example_buttons(examples: tuple[Example, ...]) -> str:
    parts: list[str] = []
    for ex in examples:
        action = ex.get("action", "ask")
        cls = ' class="search-only"' if action == "search" else ""
        action_attr = ' data-action="search"' if action == "search" else ""
        parts.append(
            f'<button type="button"{cls}{action_attr} data-q="{escape(ex["query"], quote=True)}"'
            f' title="{escape(ex["query"])}">{escape(ex["label"])}</button>'
        )
    return "".join(parts)


def _render_cards(categories: tuple[dict[str, Any], ...]) -> str:
    cards: list[str] = []
    for cat in categories:
        note = cat.get("note")
        note_html = f"<li>{escape(note)}</li>" if note else ""
        cards.append(
            f"""      <article class="help-card">
        <div class="help-card-head">
          <div class="help-card-icon">{escape(cat["icon"])}</div>
          <div>
            <h3>{escape(cat["title"])}</h3>
            <span class="help-card-tag">{escape(cat["tag"])}</span>
          </div>
        </div>
        <ul>{note_html}</ul>
        <div class="ex-btns">{_render_example_buttons(cat["examples"])}</div>
      </article>"""
        )
    return "\n".join(cards)


def render_corpus_intro(stats: dict[str, Any] | None = None) -> str:
    stats = stats or load_corpus_stats()
    docs = stats.get("docs") or 365
    chunks = stats.get("chunks") or 57235
    tokens = stats.get("tokens_fmt") or "24.6M"
    chunks_k = f"{chunks // 1000}k" if chunks >= 1000 else str(chunks)
    return (
        f"<p class=\"corpus-stats\">Corpus indexado: <b>{docs}</b> documentos · "
        f"<b>{chunks_k}</b> fragmentos · <b>{tokens}</b> tokens — "
        "matrices MRI/MSO/SPCI, FMECA, GUIGS, RCM, manuales OEM y talleres ODS1.</p>"
    )


def render_search_examples_html(*, out_dir: Path | None = None) -> str:
    stats = load_corpus_stats(out_dir)
    intro = render_corpus_intro(stats)
    corpus_cards = _render_cards(_CATEGORIES)
    tip_cards = _render_cards(_TIPS)
    return f"""  {intro}
  <details class="help corpus-examples" open>
    <summary>Ejemplos del corpus indexado</summary>
    <p class="help-intro">Consultas sobre el corpus ODS1. Clic para abrir en Consulta RAG; botones verdes = solo buscar fragmentos aquí.</p>
    <div class="help-grid">
{corpus_cards}
    </div>
  </details>
  <details class="help search-tips">
    <summary>Consejos de búsqueda</summary>
    <p class="help-intro">Cómo formular preguntas y cuándo usar cada modo.</p>
    <div class="help-grid">
{tip_cards}
    </div>
  </details>"""
