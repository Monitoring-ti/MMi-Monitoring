"""Extractor DOCX jerárquico: documento → sección → bloque."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

from mmi.index.chunking import file_sha256
from mmi.index.content_hash import block_content_hash as _block_content_hash
from mmi.ingest.docx_models import BlockQuality, DocBlock, DocumentExtract
from mmi.ingest.ocr_normalize import normalize_ocr_text
from mmi.ingest.ports import CitationAnchor, ExtractedDocument

_HEADING_RE = re.compile(r"^heading\s*(\d+)$", re.I)
_LIST_BULLET = re.compile(r"^List\s+(Bullet|Paragraph)", re.I)


def _table_markdown(headers: list[str], rows: list[list[str]]) -> str:
    if not headers:
        return ""
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(padded[: len(headers)]) + " |")
    return "\n".join(lines)


def _heading_level(style_name: str | None) -> int | None:
    if not style_name:
        return None
    m = _HEADING_RE.match(style_name.strip())
    if m:
        return int(m.group(1))
    if style_name.strip().lower() in {"title", "subtitle"}:
        return 1 if style_name.lower() == "title" else 2
    return None


def _is_list_paragraph(paragraph) -> tuple[bool, bool]:
    """Returns (is_list, is_ordered)."""
    try:
        p_pr = paragraph._p.pPr  # noqa: SLF001
        if p_pr is None or p_pr.numPr is None:
            return False, False
        ilvl = p_pr.numPr.ilvl
        level = int(ilvl.val) if ilvl is not None else 0
        _ = level
        return True, False
    except (AttributeError, ValueError):
        return False, False


def _iter_body_items(document) -> Iterator[Any]:
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    parent_elm = document.element.body
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _extract_table(table) -> tuple[list[str], list[list[str]], str]:
    rows_raw: list[list[str]] = []
    for row in table.rows:
        rows_raw.append([(cell.text or "").strip() for cell in row.cells])
    if not rows_raw:
        return [], [], ""
    headers = rows_raw[0]
    body = rows_raw[1:] if len(rows_raw) > 1 else rows_raw
    md = _table_markdown(headers, body if body != rows_raw else rows_raw)
    return headers, body, md


class DocxAdapter:
    """Extrae Word OOXML a bloques estructurados."""

    def extract(
        self,
        path: Path,
        *,
        file_hash: str | None = None,
        document_key: str | None = None,
    ) -> DocumentExtract:
        from docx import Document

        path = Path(path)
        if path.suffix.lower() == ".doc":
            from mmi.ingest.doc_convert import convert_doc_to_docx

            path = convert_doc_to_docx(path)

        file_hash = file_hash or file_sha256(path)
        doc = Document(str(path))
        notes: list[str] = []
        blocks: list[DocBlock] = []
        section_stack: list[str] = []
        position = 0
        idx = 0
        image_count = 0

        for item in _iter_body_items(doc):
            position += 1
            if item.__class__.__name__ == "Table":
                headers, rows, md = _extract_table(item)
                if not md.strip():
                    continue
                section_path = " | ".join(section_stack)
                block = DocBlock(
                    block_index=idx,
                    block_type="table",
                    text_raw=md,
                    text_normalized=normalize_ocr_text(md),
                    section_path=section_path,
                    page_or_position=position,
                    headers=headers,
                    rows=rows,
                    markdown=md,
                )
                block.block_content_hash = _block_content_hash(block)
                blocks.append(block)
                idx += 1
                continue

            paragraph = item
            text = (paragraph.text or "").strip()
            style_name = paragraph.style.name if paragraph.style else ""
            level = _heading_level(style_name)

            # Detect inline images
            has_image = False
            for run in paragraph.runs:
                if run._element.xpath(".//a:blip"):  # noqa: SLF001
                    has_image = True
                    break
            if has_image and not text:
                image_count += 1
                section_path = " | ".join(section_stack)
                block = DocBlock(
                    block_index=idx,
                    block_type="image",
                    text_raw="",
                    section_path=section_path,
                    page_or_position=position,
                    media_ref=f"image_{image_count}",
                    extraction_quality="review",
                    extra={"needs_visual_analysis": True},
                )
                block.block_content_hash = _block_content_hash(block)
                blocks.append(block)
                idx += 1
                continue

            if not text:
                continue

            is_list, ordered = _is_list_paragraph(paragraph)
            if level is not None:
                block_type = "heading"
                while section_stack and len(section_stack) >= level:
                    section_stack.pop()
                section_stack.append(text)
                section_path = " | ".join(section_stack[:-1] + [text]) if section_stack else text
            elif is_list or _LIST_BULLET.match(style_name or ""):
                block_type = "list"
                section_path = " | ".join(section_stack)
                prefix = "- " if not ordered else "1. "
                text = prefix + text
            else:
                block_type = "paragraph"
                section_path = " | ".join(section_stack)

            block = DocBlock(
                block_index=idx,
                block_type=block_type,
                text_raw=text,
                text_normalized=normalize_ocr_text(text),
                level=level,
                section_path=section_path,
                page_or_position=position,
                extra={"style": style_name, "ordered_list": ordered} if is_list else {"style": style_name},
            )
            block.block_content_hash = _block_content_hash(block)
            blocks.append(block)
            idx += 1

        # Footnotes/endnotes via footnotes part (if accessible)
        try:
            for fn in getattr(doc, "footnotes", []).footnotes or []:  # type: ignore[attr-defined]
                fn_text = (fn.text or "").strip()
                if fn_text:
                    block = DocBlock(
                        block_index=idx,
                        block_type="footnote",
                        text_raw=fn_text,
                        text_normalized=normalize_ocr_text(fn_text),
                        section_path=" | ".join(section_stack),
                    )
                    block.block_content_hash = _block_content_hash(block)
                    blocks.append(block)
                    idx += 1
        except (AttributeError, TypeError):
            pass

        pass_blocks = [b for b in blocks if b.text_raw.strip() or b.markdown.strip()]
        if not pass_blocks:
            quality: BlockQuality = "reject"
            notes.append("Documento sin bloques de texto")
        elif len(pass_blocks) < 2:
            quality = "review"
            notes.append("Contenido muy breve")
        else:
            quality = "pass"

        review_images = sum(1 for b in blocks if b.block_type == "image")
        if review_images:
            notes.append(f"{review_images} imagen(es) sin descripción (revisar/OCR selectivo)")

        return DocumentExtract(
            source_path=str(path.resolve()),
            file_hash=file_hash,
            blocks=blocks,
            quality=quality,
            notes=notes,
            meta={
                "format": "docx",
                "block_count": len(blocks),
                "blocks_pass": len(pass_blocks),
                "heading_count": sum(1 for b in blocks if b.block_type == "heading"),
                "table_count": sum(1 for b in blocks if b.block_type == "table"),
                "document_key": document_key or "",
            },
        )

    def to_extracted_document(self, extract: DocumentExtract) -> ExtractedDocument:
        parts = [f"# {Path(extract.source_path).name}", ""]
        anchors: list[CitationAnchor] = []
        current_section = ""

        for block in extract.blocks:
            if block.block_type == "heading":
                level = block.level or 1
                parts.append(f"{'#' * min(level, 4)} {block.text_raw}")
                parts.append("")
                current_section = block.section_path
                anchors.append(CitationAnchor(page_number=block.page_or_position))
            elif block.block_type == "table":
                parts.append(f"## Tabla — {block.section_path or current_section}")
                parts.append("")
                parts.append(block.markdown or block.text_raw)
                parts.append("")
            elif block.text_raw:
                if block.block_type == "list":
                    parts.append(block.text_raw)
                else:
                    parts.append(block.text_raw)
                parts.append("")

        return ExtractedDocument(
            markdown="\n".join(parts).strip() + "\n",
            quality=extract.quality,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            source_path=extract.source_path,
            anchors=anchors,
            notes=extract.notes,
            meta=extract.meta,
        )


def save_blocks_json(extract: DocumentExtract, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / "blocks.json"
    out.write_text(
        json.dumps(extract.blocks_to_json(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


def load_blocks_json(path: Path) -> list[DocBlock]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [DocBlock.from_dict(item) for item in data]


def load_or_extract(
    path: Path,
    extract_dir: Path | None = None,
    **kwargs,
) -> DocumentExtract:
    path = Path(path)
    file_hash = file_sha256(path)
    if extract_dir:
        blocks_path = extract_dir / "blocks.json"
        meta_path = extract_dir / "extracted.json"
        if blocks_path.exists() and meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if meta.get("file_hash") == file_hash:
                    blocks = load_blocks_json(blocks_path)
                    return DocumentExtract(
                        source_path=str(path.resolve()),
                        file_hash=file_hash,
                        blocks=blocks,
                        quality=meta.get("quality", "review"),
                        notes=list(meta.get("notes") or []),
                        meta=dict(meta.get("meta") or {}),
                    )
            except (OSError, json.JSONDecodeError, KeyError):
                pass
    adapter = DocxAdapter()
    return adapter.extract(path, file_hash=file_hash, **kwargs)
