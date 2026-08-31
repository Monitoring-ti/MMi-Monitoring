"""Huella de contenido normalizado (revisiones menores)."""

from __future__ import annotations

import hashlib
import re

_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", text.lower().strip())


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def block_content_hash(block) -> str:
    """Hash normalizado de un bloque DOCX."""
    parts: list[str] = [
        getattr(block, "block_type", None) or (block.get("block_type", "") if isinstance(block, dict) else ""),
        normalize_text(getattr(block, "text_raw", None) or (block.get("text_raw", "") if isinstance(block, dict) else "")),
        normalize_text(getattr(block, "markdown", None) or (block.get("markdown", "") if isinstance(block, dict) else "")),
    ]
    headers = getattr(block, "headers", None)
    if headers is None and isinstance(block, dict):
        headers = block.get("headers")
    headers = headers or []
    rows = getattr(block, "rows", None)
    if rows is None and isinstance(block, dict):
        rows = block.get("rows")
    rows = rows or []
    parts.append(normalize_text("|".join(headers)))
    for row in rows:
        parts.append(normalize_text("|".join(row)))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def slide_content_hash(slide) -> str:
    """Hash normalizado del contenido de una diapositiva (texto + tablas + notas)."""
    parts: list[str] = [
        normalize_text(slide.slide_title or ""),
        normalize_text(slide.section_title or ""),
        normalize_text(slide.speaker_notes or ""),
        normalize_text(slide.visual_summary or ""),
    ]
    for el in slide.elements:
        parts.append(el.kind)
        parts.append(normalize_text(el.text or ""))
        parts.append(normalize_text(el.markdown or ""))
        if el.headers:
            parts.append(normalize_text("|".join(el.headers)))
        for row in el.rows:
            parts.append(normalize_text("|".join(row)))
        if el.chart_title:
            parts.append(normalize_text(el.chart_title))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
