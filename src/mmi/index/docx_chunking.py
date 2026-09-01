"""Chunking para documentos Word (bloque, tabla, sección)."""

from __future__ import annotations

from mmi.index.blocks import Block
from mmi.index.chunking import (
    CHUNK_TOKENS,
    MAX_EMBED_TOKENS,
    MIN_CHUNK_TOKENS,
    ChunkOut,
    count_tokens,
    detect_assets,
    _SAFETY_RE,
)


def chunk_docx_blocks(blocks: list[Block], tipo: str) -> list[ChunkOut]:
    target = CHUNK_TOKENS.get(tipo, CHUNK_TOKENS.get("guia", 900))
    chunks: list[ChunkOut] = []
    idx = 0

    for b in blocks:
        if not b.text or not b.text.strip():
            continue
        tk = count_tokens(b.text)
        scope = (b.meta or {}).get("chunk_scope", "block")
        section = (b.meta or {}).get("section_path")
        block_type = (b.meta or {}).get("block_type", "paragraph")

        crit = "seguridad" if _SAFETY_RE.search(b.text) else "normal"

        if (
            tk <= target or scope in {"block", "table", "list", "heading", "section", "image"}
        ) and tk <= MAX_EMBED_TOKENS:
            chunks.append(
                ChunkOut(
                    content=b.text,
                    chunk_index=idx,
                    token_count=tk,
                    section_path=section,
                    criticality_level=crit,
                    asset_codes=detect_assets(b.text),
                )
            )
            idx += 1
            continue

        # Fragmentos largos: dividir por párrafos
        header_lines = b.text.split("\n")[:5]
        header = "\n".join(header_lines)
        body = "\n".join(b.text.split("\n")[5:])
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
                    section_path=section,
                    criticality_level="seguridad" if _SAFETY_RE.search(text) else "normal",
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

    filtered: list[ChunkOut] = []
    for c in chunks:
        if c.token_count >= MIN_CHUNK_TOKENS:
            filtered.append(c)
        elif filtered:
            prev = filtered[-1]
            if prev.token_count + c.token_count <= MAX_EMBED_TOKENS:
                prev.content += "\n\n" + c.content
                prev.token_count = count_tokens(prev.content)
                prev.asset_codes = sorted(set(prev.asset_codes + c.asset_codes))
                if prev.criticality_level != "seguridad" and c.criticality_level == "seguridad":
                    prev.criticality_level = "seguridad"
            else:
                filtered.append(c)
        elif c.token_count > 0:
            filtered.append(c)

    for i, c in enumerate(filtered):
        c.chunk_index = i
    return filtered
