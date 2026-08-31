"""Normalización OCR — capa de búsqueda sin destruir texto crudo."""

from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def normalize_ocr_text(text: str) -> str:
    """Limpia espacios y control; no corrige códigos técnicos."""
    if not text:
        return ""
    cleaned = _CTRL_RE.sub("", text)
    return _WS_RE.sub(" ", cleaned).strip()
