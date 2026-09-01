"""Detección de planos vs documentos narrativos antes de OCR (C4 gate)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from mmi.ingest.pdf import PageBlock, PdfAdapter

DrawingKind = Literal["plano", "documento", "mixto", "desconocido"]

_NAME_PLANO_RE = re.compile(
    r"\b(plano|planos|dwg|layout|isom|isometric|elevaci[oó]n|elevacion|corte|detalle|"
    r"diagrama|p&id|pid|lamina|lámina|ga-|me-|el-|ln-|piping|arranque|tuberia)\b",
    re.IGNORECASE,
)
_NAME_DOC_RE = re.compile(
    r"\b(instructivo|procedimiento|gu[ií]a|guia|norma|ncc|contabilidad|financier|"
    r"manual|sop|progs|check\s*list|fmeca|rcm|capacitaci[oó]n|taller)\b",
    re.IGNORECASE,
)
_ENG_DRAWING_NUM_RE = re.compile(
    r"\b\d{6,}-\d{5}-(?:\d{3}[A-Z]{2})-\d{5}\b",
    re.IGNORECASE,
)
_TEXT_PLANO_RE = re.compile(
    r"\b(plano|escala\s*1\s*:\s*\d+|detalle|corte|elevaci[oó]n|vista|nivel\s*\d+|"
    r"revision\s*de\s*plano|drawing|sheet)\b",
    re.IGNORECASE,
)
_TEXT_DOC_RE = re.compile(
    r"\b(instructivo|contabilidad|gerencia|procedimiento|activo\s+fijo|"
    r"propiedad\s+planta\s+y\s+equipo|tabla\s+de\s+contenidos|vigencia:)\b",
    re.IGNORECASE,
)
_SCALE_RE = re.compile(r"\b1\s*:\s*(\d{1,4})\b")


@dataclass
class PlanDetection:
    path: str
    is_plano: bool
    kind: DrawingKind
    confidence: float
    suggested_tipo: str
    suggested_phase0: str
    page_count: int
    pages_needs_ocr: int
    ocr_page_ratio: float
    avg_chars_per_page: float
    signals: list[str] = field(default_factory=list)
    block_ocr: bool = False
    block_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "is_plano": self.is_plano,
            "kind": self.kind,
            "confidence": round(self.confidence, 3),
            "suggested_tipo": self.suggested_tipo,
            "suggested_phase0": self.suggested_phase0,
            "page_count": self.page_count,
            "pages_needs_ocr": self.pages_needs_ocr,
            "ocr_page_ratio": round(self.ocr_page_ratio, 3),
            "avg_chars_per_page": round(self.avg_chars_per_page, 1),
            "signals": self.signals,
            "block_ocr": self.block_ocr,
            "block_reason": self.block_reason,
        }


def _sample_text(pages: list[PageBlock], max_pages: int = 2) -> str:
    parts: list[str] = []
    for block in pages[:max_pages]:
        if block.text:
            parts.append(block.text[:4000])
    return "\n".join(parts)


def _score_name(name: str) -> tuple[float, float, list[str]]:
    plano = doc = 0.0
    signals: list[str] = []
    if _NAME_PLANO_RE.search(name):
        plano += 0.35
        signals.append("nombre:indicio_plano")
    if _ENG_DRAWING_NUM_RE.search(name):
        plano += 0.45
        signals.append("nombre:codigo_ingenieria")
    if _NAME_DOC_RE.search(name):
        doc += 0.45
        signals.append("nombre:indicio_documento")
    if re.search(r"\bifc\b", name, re.I) and _NAME_DOC_RE.search(name) is None:
        # IFC en nombre no implica plano (IFC-078 instructivo financiero)
        if re.search(r"rev\s*\d+", name, re.I):
            doc += 0.15
            signals.append("nombre:ifc_revision_sin_plano")
    return plano, doc, signals


def _score_text(text: str) -> tuple[float, float, list[str]]:
    plano = doc = 0.0
    signals: list[str] = []
    if not text.strip():
        return plano, doc, signals
    if _TEXT_PLANO_RE.search(text):
        plano += 0.25
        signals.append("texto:termino_plano")
    if _SCALE_RE.search(text):
        plano += 0.2
        signals.append("texto:escala")
    if _TEXT_DOC_RE.search(text):
        doc += 0.5
        signals.append("texto:documento_narrativo")
    words = len(text.split())
    if words > 180:
        doc += 0.25
        signals.append("texto:parrafo_largo")
    return plano, doc, signals


def _score_structure(
    pages: list[PageBlock],
) -> tuple[float, float, float, float, list[str]]:
    total = len(pages) or 1
    needs_ocr = sum(1 for p in pages if p.needs_ocr)
    chars = sum(p.char_count for p in pages)
    avg = chars / total
    ratio = needs_ocr / total
    plano = doc = 0.0
    signals: list[str] = []

    if ratio >= 0.5:
        plano += 0.35
        signals.append(f"estructura:ocr_ratio={ratio:.2f}")
    elif ratio <= 0.1 and avg > 500:
        doc += 0.45
        signals.append(f"estructura:texto_nativo_denso avg={avg:.0f}")
    elif ratio <= 0.25 and avg > 800:
        doc += 0.35
        signals.append(f"estructura:documento_multipagina avg={avg:.0f}")

    if avg < 250 and ratio >= 0.3:
        plano += 0.25
        signals.append("estructura:baja_densidad_texto")

    return plano, doc, ratio, avg, signals


def detect_plan(path: Path, *, pages: list[PageBlock] | None = None) -> PlanDetection:
    """Clasifica PDF como plano escaneado vs documento narrativo."""
    path = Path(path)
    name = path.name
    if pages is None:
        if path.suffix.lower() != ".pdf" or not path.exists():
            return PlanDetection(
                path=str(path),
                is_plano=False,
                kind="desconocido",
                confidence=0.0,
                suggested_tipo="otro",
                suggested_phase0="ocr",
                page_count=0,
                pages_needs_ocr=0,
                ocr_page_ratio=0.0,
                avg_chars_per_page=0.0,
                signals=["archivo:no_pdf"],
                block_ocr=True,
                block_reason="Solo se detectan planos en PDF",
            )
        pages = PdfAdapter._read_pages(path)

    text = _sample_text(pages)
    np, nd, sig_n = _score_name(name)
    tp, td, sig_t = _score_text(text)
    sp, sd, ratio, avg, sig_s = _score_structure(pages)
    plano_score = np + tp + sp
    doc_score = nd + td + sd
    signals = sig_n + sig_t + sig_s

    if plano_score >= doc_score + 0.15:
        kind: DrawingKind = "plano"
        is_plano = True
        suggested_tipo = "plano"
        suggested_phase0 = "ocr" if ratio >= 0.3 or avg < 400 else "pdf"
        confidence = min(0.98, 0.45 + plano_score - doc_score * 0.5)
    elif doc_score >= plano_score + 0.15:
        kind = "documento"
        is_plano = False
        suggested_tipo = _infer_doc_tipo(name, text)
        suggested_phase0 = "pdf"
        confidence = min(0.98, 0.45 + doc_score - plano_score * 0.5)
    else:
        kind = "mixto" if 0.1 < ratio < 0.9 else "desconocido"
        is_plano = ratio >= 0.4 and avg < 500
        suggested_tipo = "plano" if is_plano else _infer_doc_tipo(name, text)
        suggested_phase0 = "ocr" if is_plano else "pdf"
        confidence = 0.4 + abs(plano_score - doc_score)

    block_ocr = not is_plano and doc_score >= 0.35
    block_reason = ""
    if block_ocr:
        block_reason = (
            "Documento narrativo con texto nativo denso; usar extracción PDF, no OCR de plano"
        )

    return PlanDetection(
        path=str(path.resolve()),
        is_plano=is_plano,
        kind=kind,
        confidence=confidence,
        suggested_tipo=suggested_tipo,
        suggested_phase0=suggested_phase0,
        page_count=len(pages),
        pages_needs_ocr=sum(1 for p in pages if p.needs_ocr),
        ocr_page_ratio=ratio,
        avg_chars_per_page=avg,
        signals=signals,
        block_ocr=block_ocr,
        block_reason=block_reason,
    )


def _infer_doc_tipo(name: str, text: str) -> str:
    combined = f"{name} {text[:2000]}".lower()
    if "instructivo" in combined or "contabilidad" in combined or "financier" in combined:
        return "sop"
    if "procedimiento" in combined or "progs" in combined:
        return "sop"
    if "guia" in combined or "guigs" in combined:
        return "guia"
    if "ncc" in combined or "norma" in combined:
        return "norma"
    return "manual_oem"


def assert_plano_for_ocr(path: Path, *, pages: list[PageBlock] | None = None) -> PlanDetection:
    """Gate OCR: lanza ValueError si el archivo no parece plano."""
    detection = detect_plan(path, pages=pages)
    if detection.block_ocr or not detection.is_plano:
        raise ValueError(
            f"No es plano ({detection.kind}, conf={detection.confidence:.0%}): "
            f"{detection.block_reason or 'usar phase0=pdf'}. "
            f"Señales: {', '.join(detection.signals[:5])}"
        )
    return detection
