"""Chunking adaptativo por tipo documental."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import tiktoken

from mmi.index.blocks import Block

_ENC = tiktoken.get_encoding("cl100k_base")

_SAFETY_RE = re.compile(
    r"\b(advertencia|precauci[oó]n|precauciones|peligro|atenci[oó]n|warning|"
    r"caution|danger|nota de seguridad|riesgo|loto|bloqueo|seguridad de las "
    r"personas|seguridad personal)\b",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(
    r"^\s*(\d+(?:\.\d+){0,3})\.?\s+([A-ZÁÉÍÓÚÑ][^\n]{3,70}?)\s*$"
)
_ASSET_RE = re.compile(r"\b[A-Z]{2,4}-\d{2,5}\b")

CHUNK_TOKENS = {
    "norma": 900,
    "guia": 900,
    "manual_oem": 900,
    "sop": 550,
    "tabla": 350,
    "presentacion": 500,
    "plano": 600,
    "otro": 800,
}
OVERLAP_RATIO = 0.10
MIN_CHUNK_TOKENS = 60
MIN_SLIDE_TOKENS = 40
# OpenAI text-embedding-3-* limit 8192 tokens; margen para batching
MAX_EMBED_TOKENS = 8000


def count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


def file_sha256(path: str | Path) -> str:
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
    qdrant_point_id: str | None = None


@dataclass
class _Seg:
    text: str
    page: int
    section: str
    is_heading: bool = False


def _segment_pdf(blocks: list[Block]) -> list[_Seg]:
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
                segs.append(_Seg(text=line, page=b.page or 0, section=current_section, is_heading=True))
                continue
            for s in re.split(r"(?<=[.!?])\s+", line):
                s = s.strip()
                if s:
                    segs.append(_Seg(text=s, page=b.page or 0, section=current_section))
    return segs


def chunk_pdf_blocks(blocks: list[Block], tipo: str) -> list[ChunkOut]:
    target = CHUNK_TOKENS.get(tipo, 800)
    overlap = int(target * OVERLAP_RATIO)
    segs = _segment_pdf(blocks)
    chunks: list[ChunkOut] = []
    buf: list[_Seg] = []
    buf_tokens = 0
    idx = 0

    def flush():
        nonlocal buf, buf_tokens, idx
        if not buf:
            return
        text = " ".join(s.text for s in buf)
        tk = count_tokens(text)
        if tk < MIN_CHUNK_TOKENS and chunks:
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
        chunks.append(
            ChunkOut(
                content=text,
                chunk_index=idx,
                token_count=tk,
                page_start=min(pages) if pages else None,
                page_end=max(pages) if pages else None,
                section_path=section,
                criticality_level=crit,
                asset_codes=detect_assets(text),
            )
        )
        idx += 1
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
        new_section = s.is_heading and buf and buf_tokens >= target * 0.5
        if (buf_tokens + tk > target and buf) or new_section:
            flush()
        buf.append(s)
        buf_tokens += tk
        if _SAFETY_RE.search(s.text) and i + 1 < len(segs):
            nxt = segs[i + 1]
            if not nxt.is_heading:
                buf.append(nxt)
                buf_tokens += count_tokens(nxt.text)
                i += 1
        i += 1
    flush()
    for i, c in enumerate(chunks):
        c.chunk_index = i
    return chunks


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
        chunks.append(
            ChunkOut(
                content=text,
                chunk_index=idx,
                token_count=count_tokens(text),
                section_path=sheet,
                criticality_level="normal",
                asset_codes=detect_assets(text),
            )
        )
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


def split_oversized_text(text: str, max_tokens: int = MAX_EMBED_TOKENS) -> list[str]:
    """Divide texto que excede el límite del modelo de embeddings."""
    if count_tokens(text) <= max_tokens:
        return [text]
    parts: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    for para in (p.strip() for p in text.split("\n\n") if p.strip()):
        pt = count_tokens(para)
        if pt > max_tokens:
            if buf:
                parts.append("\n\n".join(buf))
                buf, buf_tokens = [], 0
            for sent in re.split(r"(?<=[.!?])\s+", para):
                sent = sent.strip()
                if not sent:
                    continue
                st = count_tokens(sent)
                if st > max_tokens:
                    tokens = _ENC.encode(sent)
                    for i in range(0, len(tokens), max_tokens):
                        parts.append(_ENC.decode(tokens[i : i + max_tokens]))
                else:
                    if buf_tokens + st > max_tokens and buf:
                        parts.append(" ".join(buf))
                        buf, buf_tokens = [], 0
                    buf.append(sent)
                    buf_tokens += st
            continue
        if buf_tokens + pt > max_tokens and buf:
            parts.append("\n\n".join(buf))
            buf, buf_tokens = [], 0
        buf.append(para)
        buf_tokens += pt
    if buf:
        parts.append("\n\n".join(buf) if "\n" in "\n\n".join(buf) else " ".join(buf))
    return parts or [text]


def enforce_max_embed_size(
    chunks: list[ChunkOut],
    max_tokens: int = MAX_EMBED_TOKENS,
) -> list[ChunkOut]:
    """Garantiza que ningún chunk supere el límite de tokens del embedder."""
    out: list[ChunkOut] = []
    for c in chunks:
        if c.token_count <= max_tokens:
            out.append(c)
            continue
        for part in split_oversized_text(c.content, max_tokens):
            out.append(
                ChunkOut(
                    content=part,
                    chunk_index=0,
                    token_count=count_tokens(part),
                    page_start=c.page_start,
                    page_end=c.page_end,
                    section_path=c.section_path,
                    criticality_level=c.criticality_level,
                    asset_codes=detect_assets(part),
                )
            )
    for i, c in enumerate(out):
        c.chunk_index = i
    return out


def chunk_blocks(blocks: list[Block], fmt: str, tipo: str) -> list[ChunkOut]:
    if fmt in {".docx", ".doc"}:
        from mmi.index.docx_chunking import chunk_docx_blocks

        chunks = chunk_docx_blocks(blocks, tipo)
    elif fmt == ".pdf":
        chunks = chunk_pdf_blocks(blocks, tipo)
    elif fmt in {".xlsx", ".xls"}:
        chunks = chunk_xlsx_blocks(blocks, tipo)
    elif fmt == ".pptx":
        from mmi.index.pptx_chunking import chunk_pptx_blocks

        chunks = chunk_pptx_blocks(blocks, tipo)
    else:
        raise ValueError(f"Formato no soportado para chunking: {fmt}")
    return enforce_max_embed_size(chunks)
