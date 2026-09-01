"""Chunking para presentaciones PPTX (slide, elemento, sección)."""

from __future__ import annotations

from mmi.index.blocks import Block
from mmi.index.chunking import (
    CHUNK_TOKENS,
    MAX_EMBED_TOKENS,
    MIN_SLIDE_TOKENS,
    ChunkOut,
    count_tokens,
    detect_assets,
)


def chunk_pptx_blocks(blocks: list[Block], tipo: str) -> list[ChunkOut]:
    target = CHUNK_TOKENS.get(tipo, CHUNK_TOKENS["presentacion"])
    chunks: list[ChunkOut] = []
    idx = 0

    for b in blocks:
        if not b.text or not b.text.strip():
            continue
        tk = count_tokens(b.text)
        scope = (b.meta or {}).get("chunk_scope", "slide")
        slide_num = b.slide
        slide_title = (b.meta or {}).get("slide_title")
        section = (b.meta or {}).get("section_title")

        if (tk <= target or scope in {"slide", "element", "section"}) and tk <= MAX_EMBED_TOKENS:
            section_path = _section_path(section, slide_title, slide_num)
            chunks.append(
                ChunkOut(
                    content=b.text,
                    chunk_index=idx,
                    token_count=tk,
                    page_start=slide_num,
                    page_end=slide_num,
                    section_path=section_path,
                    criticality_level="normal",
                    asset_codes=detect_assets(b.text),
                )
            )
            idx += 1
            continue

        # Fallback: dividir texto largo preservando encabezado de slide
        header_lines = b.text.split("\n")[:4]
        header = "\n".join(header_lines)
        body = "\n".join(b.text.split("\n")[4:])
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        buf: list[str] = []
        buf_tokens = 0

        def flush():
            nonlocal buf, buf_tokens, idx
            if not buf:
                return
            text = header + "\n\n" + "\n\n".join(buf)
            chunks.append(
                ChunkOut(
                    content=text,
                    chunk_index=idx,
                    token_count=count_tokens(text),
                    page_start=slide_num,
                    page_end=slide_num,
                    section_path=_section_path(section, slide_title, slide_num),
                    criticality_level="normal",
                    asset_codes=detect_assets(text),
                )
            )
            idx += 1
            buf, buf_tokens = [], 0

        for para in paragraphs:
            pt = count_tokens(para)
            if buf_tokens + pt > target and buf:
                flush()
            buf.append(para)
            buf_tokens += pt
        flush()

    # Descartar fragmentos demasiado pequeños sin contexto
    filtered: list[ChunkOut] = []
    for c in chunks:
        if c.token_count >= MIN_SLIDE_TOKENS:
            filtered.append(c)
        elif filtered:
            prev = filtered[-1]
            if prev.token_count + c.token_count <= MAX_EMBED_TOKENS:
                prev.content += "\n\n" + c.content
                prev.token_count = count_tokens(prev.content)
                prev.asset_codes = sorted(set(prev.asset_codes + c.asset_codes))
            else:
                filtered.append(c)
        elif c.token_count > 0:
            filtered.append(c)

    for i, c in enumerate(filtered):
        c.chunk_index = i
    return filtered


def _section_path(
    section: str | None,
    slide_title: str | None,
    slide_num: int | None,
) -> str | None:
    parts: list[str] = []
    if section:
        parts.append(section)
    if slide_num is not None:
        label = slide_title or f"Diapositiva {slide_num}"
        parts.append(f"Slide {slide_num}: {label}")
    return " | ".join(parts) if parts else None
