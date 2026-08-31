"""Normalización contextual: bloques DOCX → texto para chunking RAG."""

from __future__ import annotations

from collections import defaultdict

from mmi.index.blocks import Block
from mmi.ingest.docx_models import DocBlock, DocumentExtract


def _context_header(
    *,
    document_name: str,
    version_label: str,
    document_key: str,
    section_path: str,
    tipo: str,
    block_index: int | None = None,
) -> str:
    lines = [f"Documento: {document_name} | Versión: {version_label}"]
    if section_path:
        lines.append(f"Sección: {section_path}")
    if block_index is not None:
        lines.append(f"Bloque: {block_index}")
    meta = [f"clave={document_key}", f"tipo={tipo}"]
    lines.append(f"Metadatos: {' | '.join(meta)}")
    return "\n".join(lines)


def block_to_context_text(
    block: DocBlock,
    *,
    document_name: str,
    version_label: str,
    document_key: str,
    tipo: str = "guia",
) -> str:
    header = _context_header(
        document_name=document_name,
        version_label=version_label,
        document_key=document_key,
        section_path=block.section_path,
        tipo=tipo,
        block_index=block.block_index,
    )
    parts = [header, ""]
    if block.block_type == "table":
        parts.append("Tabla:")
        parts.append(block.markdown or block.text_raw)
    elif block.block_type == "heading":
        level = block.level or 1
        parts.append(f"{'#' * min(level, 4)} {block.text_raw}")
    elif block.block_type == "list":
        parts.append("Lista:")
        parts.append(block.text_raw)
    elif block.block_type == "footnote":
        parts.append("Nota al pie:")
        parts.append(block.text_raw)
    elif block.block_type == "image":
        parts.append("Imagen (sin texto extraído):")
        if block.media_ref:
            parts.append(f"Ref: {block.media_ref}")
    else:
        parts.append("Contenido:")
        parts.append(block.text_raw)
    return "\n".join(parts).strip()


def blocks_to_blocks(
    extract: DocumentExtract,
    *,
    document_key: str = "",
    version_label: str = "",
    tipo: str = "guia",
    dense_block_token_threshold: int = 450,
) -> list[Block]:
    """Convierte bloques DOCX a Block indexables; bloques densos se parten por tipo."""
    from mmi.index.chunking import count_tokens

    name = extract.source_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    blocks: list[Block] = []

    for block in extract.blocks:
        if block.extraction_quality == "reject":
            continue
        if block.block_type == "image" and not block.text_raw.strip():
            blocks.append(
                Block(
                    text=block_to_context_text(
                        block,
                        document_name=name,
                        version_label=version_label,
                        document_key=document_key,
                        tipo=tipo,
                    ),
                    meta={
                        "block_index": block.block_index,
                        "section_path": block.section_path,
                        "block_type": block.block_type,
                        "block_content_hash": block.block_content_hash,
                        "chunk_scope": "image",
                        "needs_visual_analysis": True,
                    },
                )
            )
            continue

        text = block.markdown or block.text_raw
        if not text.strip():
            continue

        full = block_to_context_text(
            block,
            document_name=name,
            version_label=version_label,
            document_key=document_key,
            tipo=tipo,
        )
        tk = count_tokens(full)
        scope = "block"
        if block.block_type == "table":
            scope = "table"
        elif block.block_type == "heading":
            scope = "heading"

        if tk <= dense_block_token_threshold or block.block_type in {"table", "list", "heading"}:
            blocks.append(
                Block(
                    text=full,
                    meta={
                        "block_index": block.block_index,
                        "section_path": block.section_path,
                        "block_type": block.block_type,
                        "block_content_hash": block.block_content_hash,
                        "level": block.level,
                        "chunk_scope": scope,
                    },
                )
            )
            continue

        # Párrafo denso: dividir por oraciones
        header = _context_header(
            document_name=name,
            version_label=version_label,
            document_key=document_key,
            section_path=block.section_path,
            tipo=tipo,
            block_index=block.block_index,
        )
        sentences = [s.strip() for s in block.text_raw.replace("\n", " ").split(". ") if s.strip()]
        buf: list[str] = []
        for sent in sentences:
            piece = f"{header}\n\nContenido:\n" + ". ".join(buf + [sent])
            if count_tokens(piece) > dense_block_token_threshold and buf:
                blocks.append(
                    Block(
                        text=f"{header}\n\nContenido:\n" + ". ".join(buf),
                        meta={
                            "block_index": block.block_index,
                            "section_path": block.section_path,
                            "block_type": block.block_type,
                            "block_content_hash": block.block_content_hash,
                            "chunk_scope": "fragment",
                        },
                    )
                )
                buf = [sent]
            else:
                buf.append(sent)
        if buf:
            blocks.append(
                Block(
                    text=f"{header}\n\nContenido:\n" + ". ".join(buf),
                    meta={
                        "block_index": block.block_index,
                        "section_path": block.section_path,
                        "block_type": block.block_type,
                        "block_content_hash": block.block_content_hash,
                        "chunk_scope": "fragment",
                    },
                )
            )

    return blocks


def section_aggregate_blocks(
    extract: DocumentExtract,
    *,
    document_key: str = "",
    version_label: str = "",
    tipo: str = "guia",
    min_blocks_per_section: int = 3,
) -> list[Block]:
    """Fragmentos agrupados por sección para consultas multi-bloque."""
    by_section: dict[str, list[DocBlock]] = defaultdict(list)
    for block in extract.blocks:
        if block.extraction_quality == "reject":
            continue
        key = block.section_path or "Sin sección"
        if block.block_type == "heading" and block.text_raw:
            key = block.section_path or block.text_raw
        by_section[key].append(block)

    name = extract.source_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    blocks: list[Block] = []
    for section, section_blocks in by_section.items():
        content_blocks = [b for b in section_blocks if b.block_type != "heading"]
        if len(content_blocks) < min_blocks_per_section:
            continue
        parts = [
            f"Documento: {name} | Versión: {version_label}",
            f"Sección: {section}",
            f"Metadatos: clave={document_key} | tipo={tipo}",
            "",
        ]
        for block in section_blocks:
            text = block.markdown or block.text_raw
            if not text.strip():
                continue
            if block.block_type == "heading":
                parts.append(f"## {text}")
            elif block.block_type == "table":
                parts.append("### Tabla")
                parts.append(text)
            else:
                parts.append(text)
            parts.append("")

        text = "\n".join(parts).strip()
        if text:
            blocks.append(
                Block(
                    text=text,
                    meta={
                        "section_path": section,
                        "chunk_scope": "section",
                        "block_count": len(content_blocks),
                    },
                )
            )
    return blocks
