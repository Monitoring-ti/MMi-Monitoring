#!/usr/bin/env python3
"""
MMI — Fase 2 · Chunking adaptativo refinado por dominio.

Mejoras respecto a la Fase 1:
  - Detección de secciones numeradas (p.ej. "8.2.3 Codificación") para
    rellenar section_path y anclar los cortes a la estructura del documento.
  - Cortes semánticos: se prefiere cortar en límite de sección o de párrafo,
    no a media frase.
  - Guardas de seguridad reforzadas: una advertencia se mantiene con su paso
    y el chunk se etiqueta 'seguridad'.
  - Tamaños por dominio ajustados según el análisis del lote 1.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import tiktoken

from extractors import Block

_ENC = tiktoken.get_encoding("cl100k_base")

# Palabras que marcan una advertencia de seguridad
_SAFETY_RE = re.compile(
    r"\b(advertencia|precauci[oó]n|precauciones|peligro|atenci[oó]n|warning|"
    r"caution|danger|nota de seguridad|riesgo|loto|bloqueo|seguridad de las "
    r"personas|seguridad personal)\b",
    re.IGNORECASE,
)

# Encabezado de sección numerada: "8.2.3 Codificación" o "8. DESCRIPCIÓN"
_SECTION_RE = re.compile(
    r"^\s*(\d+(?:\.\d+){0,3})\.?\s+([A-ZÁÉÍÓÚÑ][^\n]{3,70}?)\s*$"
)

# Códigos de activo (BOM-210, CH-430, IFC-78)
_ASSET_RE = re.compile(r"\b[A-Z]{2,4}-\d{2,5}\b")

# Tamaños objetivo de chunk (tokens) por tipo — refinados con el análisis
CHUNK_TOKENS = {
    "norma": 900,
    "guia": 900,
    "manual_oem": 900,
    "sop": 550,
    "tabla": 350,
    "presentacion": 500,
    "otro": 800,
}
OVERLAP_RATIO = 0.10
MIN_CHUNK_TOKENS = 60   # PDF: por debajo, se fusiona con el siguiente
MIN_SLIDE_TOKENS = 40   # PPTX: por debajo, se fusiona con la siguiente slide


def count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_assets(text: str) -> list[str]:
    return sorted(set(_ASSET_RE.findall(text)))


@dataclass
class ChunkOut:
    content: str
    chunk_index: int
    token_count: int
    page_start: int | None = None
    page_end: int | None = None
    section_path: str | None = None
    criticality_level: str = "normal"
    asset_codes: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------
# Segmentos de texto con metadatos de sección y página
# ----------------------------------------------------------------------------

@dataclass
class _Seg:
    text: str
    page: int
    section: str
    is_heading: bool = False


def _segment_pdf(blocks: list[Block]) -> list[_Seg]:
    """Convierte bloques de página en segmentos de párrafo/frase, rastreando la
    sección vigente a partir de los encabezados numerados."""
    segs: list[_Seg] = []
    current_section = ""
    for b in blocks:
        if b.needs_ocr or not b.text:
            continue
        for line in b.text.split("\n"):
            line = line.strip()
            if not line:
                continue
            m = _SECTION_RE.match(line)
            if m:
                num, title = m.group(1), m.group(2).strip()
                current_section = f"{num} {title}"
                segs.append(_Seg(text=line, page=b.page or 0,
                                 section=current_section, is_heading=True))
                continue
            # Dividir párrafos largos en frases
            for s in re.split(r"(?<=[.!?])\s+", line):
                s = s.strip()
                if s:
                    segs.append(_Seg(text=s, page=b.page or 0,
                                     section=current_section))
    return segs


def chunk_pdf_blocks(blocks: list[Block], tipo: str) -> list[ChunkOut]:
    """Chunking de texto corrido con cortes en límite de sección y guardas de
    seguridad (advertencia + paso juntos)."""
    target = CHUNK_TOKENS.get(tipo, 800)
    overlap = int(target * OVERLAP_RATIO)
    segs = _segment_pdf(blocks)

    chunks: list[ChunkOut] = []
    buf: list[_Seg] = []
    buf_tokens = 0
    idx = 0

    def flush():
        nonlocal buf, buf_tokens, idx
        # Fusionar buffers demasiado cortos con el anterior
        if not buf:
            return
        text = " ".join(s.text for s in buf)
        tk = count_tokens(text)
        if tk < MIN_CHUNK_TOKENS and chunks:
            # anexar al chunk anterior
            prev = chunks[-1]
            prev.content += " " + text
            prev.token_count = count_tokens(prev.content)
            prev.page_end = max(prev.page_end or 0, max((s.page for s in buf), default=0))
            if prev.criticality_level != "seguridad" and _SAFETY_RE.search(text):
                prev.criticality_level = "seguridad"
            prev.asset_codes = sorted(set(prev.asset_codes + detect_assets(text)))
            buf, buf_tokens = [], 0
            return
        pages = [s.page for s in buf if s.page]
        section = next((s.section for s in reversed(buf) if s.section), None)
        crit = "seguridad" if _SAFETY_RE.search(text) else "normal"
        chunks.append(ChunkOut(
            content=text, chunk_index=idx, token_count=tk,
            page_start=min(pages) if pages else None,
            page_end=max(pages) if pages else None,
            section_path=section, criticality_level=crit,
            asset_codes=detect_assets(text),
        ))
        idx += 1
        # Solape: conservar la cola del buffer
        if overlap > 0:
            kept, acc = [], 0
            for s in reversed(buf):
                t = count_tokens(s.text)
                if acc + t > overlap:
                    break
                kept.insert(0, s)
                acc += t
            buf, buf_tokens = kept, acc
        else:
            buf, buf_tokens = [], 0

    i = 0
    while i < len(segs):
        s = segs[i]
        tk = count_tokens(s.text)
        # Corte preferente al cambiar de sección (si el buffer ya tiene masa)
        new_section = s.is_heading and buf and buf_tokens >= target * 0.5
        if (buf_tokens + tk > target and buf) or new_section:
            flush()
        buf.append(s)
        buf_tokens += tk
        # Guarda de seguridad: incluir el segmento siguiente (el paso)
        if _SAFETY_RE.search(s.text) and i + 1 < len(segs):
            nxt = segs[i + 1]
            if not nxt.is_heading:
                buf.append(nxt)
                buf_tokens += count_tokens(nxt.text)
                i += 1
        i += 1
    flush()
    # Reindexar tras posibles fusiones
    for i, c in enumerate(chunks):
        c.chunk_index = i
    return chunks


# ----------------------------------------------------------------------------
# XLSX y PPTX (sin cambios estructurales; tamaños refinados)
# ----------------------------------------------------------------------------

def chunk_xlsx_blocks(blocks: list[Block], tipo: str) -> list[ChunkOut]:
    target = CHUNK_TOKENS.get(tipo, 350)
    chunks: list[ChunkOut] = []
    buf: list[str] = []
    buf_tokens = 0
    idx = 0
    sheet = blocks[0].sheet if blocks else None

    def flush():
        nonlocal buf, buf_tokens, idx
        if not buf:
            return
        text = "\n".join(buf)
        chunks.append(ChunkOut(
            content=text, chunk_index=idx, token_count=count_tokens(text),
            section_path=sheet, criticality_level="normal",
            asset_codes=detect_assets(text),
        ))
        idx += 1
        buf, buf_tokens = [], 0

    for b in blocks:
        tk = count_tokens(b.text)
        if buf_tokens + tk > target and buf:
            flush()
        buf.append(b.text)
        buf_tokens += tk
    flush()
    return chunks


def chunk_pptx_blocks(blocks: list[Block], tipo: str) -> list[ChunkOut]:
    """Un chunk por slide; las slides muy cortas se fusionan con la siguiente."""
    chunks: list[ChunkOut] = []
    pending = ""
    pending_slide = None
    idx = 0
    for b in blocks:
        text = b.text or ""
        if b.notes:
            text = f"{text}\n\n[Notas del orador]\n{b.notes}".strip()
        if not text:
            continue
        candidate = (pending + "\n" + text).strip() if pending else text
        if count_tokens(candidate) < MIN_SLIDE_TOKENS:
            # demasiado corto: acumular con la siguiente slide
            pending = candidate
            pending_slide = pending_slide or b.slide
            continue
        crit = "seguridad" if _SAFETY_RE.search(candidate) else "normal"
        chunks.append(ChunkOut(
            content=candidate, chunk_index=idx, token_count=count_tokens(candidate),
            page_start=pending_slide or b.slide, page_end=b.slide,
            section_path=f"Slide {pending_slide or b.slide}"
                         + (f"–{b.slide}" if pending_slide and pending_slide != b.slide else ""),
            criticality_level=crit, asset_codes=detect_assets(candidate),
        ))
        idx += 1
        pending, pending_slide = "", None
    if pending:
        crit = "seguridad" if _SAFETY_RE.search(pending) else "normal"
        chunks.append(ChunkOut(
            content=pending, chunk_index=idx, token_count=count_tokens(pending),
            page_start=pending_slide, page_end=pending_slide,
            section_path=f"Slide {pending_slide}", criticality_level=crit,
            asset_codes=detect_assets(pending),
        ))
    return chunks


def chunk_blocks(blocks: list[Block], fmt: str, tipo: str) -> list[ChunkOut]:
    if fmt == ".pdf":
        return chunk_pdf_blocks(blocks, tipo)
    if fmt == ".docx":
        return chunk_pdf_blocks(blocks, tipo)  # texto corrido, misma lógica
    if fmt == ".xlsx":
        return chunk_xlsx_blocks(blocks, tipo)
    if fmt == ".pptx":
        return chunk_pptx_blocks(blocks, tipo)
    raise ValueError(f"Formato no soportado para chunking: {fmt}")


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from extractors import extract
    path = sys.argv[1]
    tipo = sys.argv[2] if len(sys.argv) > 2 else "otro"
    fmt = os.path.splitext(path)[1].lower()
    ch = chunk_blocks(extract(path), fmt, tipo)
    total = sum(c.token_count for c in ch)
    seg = sum(1 for c in ch if c.criticality_level == "seguridad")
    con_sec = sum(1 for c in ch if c.section_path)
    print(f"{os.path.basename(path)} [{tipo}]: {len(ch)} chunks, {total} tokens, "
          f"{seg} seguridad, {con_sec} con section_path")
