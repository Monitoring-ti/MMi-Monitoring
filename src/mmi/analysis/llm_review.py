"""Revisión asistida de extracciones rechazadas / con error (OpenRouter)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mmi.llm.openrouter import chat_completion

REVIEW_MODELS: list[dict[str, str]] = [
    {"id": "openai/gpt-4o-mini", "label": "GPT-4o mini (rápido, económico)"},
    {"id": "openai/gpt-4o", "label": "GPT-4o (mejor calidad)"},
    {"id": "anthropic/claude-3.5-sonnet", "label": "Claude 3.5 Sonnet"},
    {"id": "google/gemini-2.0-flash-001", "label": "Gemini 2.0 Flash"},
    {"id": "deepseek/deepseek-chat", "label": "DeepSeek Chat (económico)"},
]

SYSTEM_PROMPT = """Eres un revisor de calidad de extracción documental para un sistema RAG industrial (NCC-30, mantenibilidad, confiabilidad).

Evalúa si el documento extraído es apto para indexación semántica o qué acción recomiendas.

Responde SOLO JSON válido (sin markdown) con esta forma:
{
  "verdict": "pass|review|reject|reextract|exclude",
  "suggested_quality": "pass|review|reject",
  "confidence": 0.0-1.0,
  "summary": "1-2 oraciones",
  "issues": ["..."],
  "recommendations": ["..."],
  "alternatives": ["reextract", "ocr", "manual_review", "exclude", "index_anyway"]
}

Criterios:
- pass: contenido útil y estructura suficiente para citas
- review: usable con reservas (parcial, ruido, tablas rotas)
- reject: plantilla vacía, corrupto, sin texto indexable
- reextract: conviene repetir Fase 0 (archivo cambió, extractor falló)
- exclude: fuera del corpus / duplicado / no aplica al análisis
"""


def _load_extraction_context(extract_dir: Path, max_chars: int = 12_000) -> dict[str, Any]:
    meta_path = extract_dir / "extracted.json"
    if not meta_path.exists():
        return {"error": "Sin extracted.json"}
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    md_path = extract_dir / "extracted.md"
    md = ""
    if md_path.exists():
        md = md_path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    notes = list(data.get("notes") or [])
    meta = data.get("meta") or {}
    return {
        "format": data.get("format") or meta.get("format"),
        "quality": data.get("quality"),
        "notes": notes,
        "meta": meta,
        "markdown_preview": md,
        "source_path": data.get("source_path"),
    }


def review_extraction(
    extract_dir: Path,
    *,
    document_name: str = "",
    index_error: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    ctx = _load_extraction_context(extract_dir)
    if ctx.get("error"):
        return {"ok": False, "error": ctx["error"]}

    user_msg = (
        f"Documento: {document_name or ctx.get('source_path', '')}\n"
        f"Formato: {ctx.get('format')}\n"
        f"Calidad Fase 0: {ctx.get('quality')}\n"
        f"Notas extractor: {json.dumps(ctx.get('notes') or [], ensure_ascii=False)}\n"
        f"Meta: {json.dumps(ctx.get('meta') or {}, ensure_ascii=False)[:2000]}\n"
    )
    if index_error:
        user_msg += f"Error indexación: {index_error}\n"
    user_msg += f"\nVista previa extraída:\n{ctx.get('markdown_preview', '')[:8000]}"

    used_model = model or REVIEW_MODELS[0]["id"]
    try:
        raw, usage = chat_completion(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            model=used_model,
            temperature=0.1,
            max_tokens=900,
            return_usage=True,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "model": used_model}

    parsed: dict[str, Any] | None = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError:
                parsed = None

    result: dict[str, Any] = {
        "ok": True,
        "model": used_model,
        "document": document_name,
        "raw": raw if not parsed else None,
        "usage": usage,
    }
    if parsed:
        result.update(parsed)
    else:
        result["summary"] = raw[:500]
        result["verdict"] = "review"
        result["suggested_quality"] = "review"

    review_path = extract_dir / "ai-review.json"
    review_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["review_path"] = str(review_path)
    return result
