"""Chunking contextualizado para texto OCR (C4.10)."""

from __future__ import annotations

from mmi.config import get_ocr_settings
from mmi.index.chunking import ChunkOut, count_tokens, detect_assets
from mmi.ingest.ocr_models import OcrBlock, OcrPage


def _chunk_header(
    *,
    document_name: str,
    document_key: str,
    version_label: str,
    page_number: int,
    block: OcrBlock,
    tipo: str,
    language: str | None,
) -> str:
    region = f"bloque b{block.block_index}"
    if block.block_type == "table":
        region = f"tabla t{block.block_index}"
    conf = f"{block.confidence:.2f}" if block.confidence is not None else "?"
    parts = [
        f"Documento: {document_name}",
        f"Versión: {version_label or 'vigente'}",
        f"Página {page_number}",
        f"Región: {region}",
        f"Tipo: {tipo}",
    ]
    if language:
        parts.append(f"Idioma: {language}")
    assets = detect_assets(block.text_normalized or block.text_raw)
    if assets:
        parts.append(f"Activo: {', '.join(assets[:3])}")
    parts.append(f"Confianza bloque: {conf}")
    return " | ".join(parts)


def ocr_block_to_chunk(
    page: OcrPage,
    block: OcrBlock,
    *,
    document_name: str,
    document_key: str = "",
    version_label: str = "",
    tipo: str = "plano",
    chunk_index: int,
) -> ChunkOut | None:
    settings = get_ocr_settings()
    if block.confidence is not None and block.confidence < settings.min_block_confidence:
        return None
    body = (block.text_normalized or block.text_raw or "").strip()
    if not body:
        return None
    header = _chunk_header(
        document_name=document_name,
        document_key=document_key,
        version_label=version_label,
        page_number=page.page_number,
        block=block,
        tipo=tipo,
        language=page.language,
    )
    content = f"{header}\n\n{body}"
    return ChunkOut(
        content=content,
        chunk_index=chunk_index,
        token_count=count_tokens(content),
        page_start=page.page_number,
        page_end=page.page_number,
        section_path=f"p{page.page_number}/b{block.block_index}",
        asset_codes=detect_assets(body),
        criticality_level="normal",
    )


def _blocks_for_chunking(page: OcrPage) -> list[OcrBlock]:
    """Agrupa líneas OCR en un párrafo por página (evita miles de chunks)."""
    blocks = list(page.blocks or [])
    lines = [b for b in blocks if b.block_type == "line"]
    others = [b for b in blocks if b.block_type != "line"]
    if len(lines) >= 2:
        raw = "\n".join((b.text_raw or "").strip() for b in lines if (b.text_raw or "").strip())
        norm = " ".join(
            (b.text_normalized or b.text_raw or "").strip() for b in lines if (b.text_raw or b.text_normalized)
        )
        confs = [b.confidence for b in lines if b.confidence is not None]
        conf = sum(confs) / len(confs) if confs else page.confidence
        merged = [
            OcrBlock(
                block_index=0,
                block_type="paragraph",
                text_raw=raw,
                text_normalized=norm,
                confidence=conf,
            )
        ]
        return merged + others
    if blocks:
        return blocks
    if page.text_normalized or page.text_raw:
        return [
            OcrBlock(
                block_index=0,
                block_type="paragraph",
                text_raw=page.text_raw,
                text_normalized=page.text_normalized or page.text_raw,
                confidence=page.confidence,
            )
        ]
    return []


def chunk_ocr_pages(
    pages: list[OcrPage],
    *,
    document_name: str,
    document_key: str = "",
    version_label: str = "",
    tipo: str = "plano",
) -> list[ChunkOut]:
    """Genera chunks indexables desde páginas OCR validadas."""
    chunks: list[ChunkOut] = []
    idx = 0
    for page in pages:
        if page.status == "reject":
            continue
        blocks = _blocks_for_chunking(page)
        for block in blocks:
            chunk = ocr_block_to_chunk(
                page,
                block,
                document_name=document_name,
                document_key=document_key,
                version_label=version_label,
                tipo=tipo,
                chunk_index=idx,
            )
            if chunk:
                chunks.append(chunk)
                idx += 1
    return chunks
