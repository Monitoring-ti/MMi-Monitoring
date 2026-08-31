"""Análisis visual selectivo de diapositivas (stub — OCR/visión en Fase C)."""

from __future__ import annotations

from pathlib import Path

from mmi.ingest.pptx_models import SlideElement


def maybe_describe_visual(
    element: SlideElement,
    source_path: Path,
    slide_number: int,
) -> str | None:
    """Genera descripción solo si está habilitado y el elemento lo requiere."""
    if not element.needs_visual_analysis:
        return None
    # Fase C: OCR / modelo de visión sobre media exportada.
    # B3: no describir automáticamente — marcar para revisión humana.
    return None
