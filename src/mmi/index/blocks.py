"""Bloques de texto con procedencia para chunking."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Block:
    text: str
    page: int | None = None
    sheet: str | None = None
    row: int | None = None
    slide: int | None = None
    notes: str | None = None
    needs_ocr: bool = False
    meta: dict = field(default_factory=dict)


from mmi.analysis.extract_index import default_extract_roots


def _resolve_extract_dir(path: Path, extract_root: Path | None = None) -> Path | None:
    from mmi.analysis.status import _find_extract_dir

    if extract_root is not None:
        return _find_extract_dir(extract_root, str(path.resolve()))
    for root in default_extract_roots():
        hit = _find_extract_dir(root, str(path.resolve()))
        if hit:
            return hit
    return None


def blocks_from_path(
    path: Path,
    *,
    extract_root: Path | None = None,
    document_key: str = "",
    version_label: str = "",
    tipo: str = "presentacion",
) -> list[Block]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        extract_dir = _resolve_extract_dir(path, extract_root)

        if extract_dir and (extract_dir / "extracted.json").exists():
            import json

            data = json.loads((extract_dir / "extracted.json").read_text(encoding="utf-8"))
            if data.get("format") == "ocr" and data.get("pages"):
                blocks = []
                name = path.name
                for pg in data["pages"]:
                    page_num = pg.get("page", 0)
                    text = pg.get("text") or pg.get("text_raw") or ""
                    if not text.strip():
                        continue
                    header = (
                        f"Documento: {name} | Página {page_num}\n"
                        f"Confianza OCR: {pg.get('confidence', '?')}\n\n"
                    )
                    blocks.append(
                        Block(
                            text=header + text,
                            page=page_num,
                            meta={
                                "text_raw": pg.get("text_raw"),
                                "confidence": pg.get("confidence"),
                                "format": "ocr",
                            },
                        )
                    )
                if blocks:
                    return blocks

        from mmi.ingest.pdf import PdfAdapter

        pages = PdfAdapter._read_pages(path)
        ocr_needed = [p for p in pages if p.needs_ocr]
        if ocr_needed and len(ocr_needed) == len(pages):
            from mmi.ingest.ocr import extract_with_ocr

            doc = extract_with_ocr(path)
            return [
                Block(
                    text=(
                        f"Documento: {path.name} | Página {pg.get('page')}\n"
                        f"Confianza OCR: {pg.get('confidence', '?')}\n\n"
                        f"{pg.get('text') or pg.get('text_raw', '')}"
                    ),
                    page=pg.get("page"),
                    meta={"format": "ocr", "confidence": pg.get("confidence")},
                )
                for pg in (doc.meta.get("pages") or [])
                if (pg.get("text") or pg.get("text_raw", "")).strip()
            ]
        return [
            Block(text=p.text, page=p.page, needs_ocr=p.needs_ocr)
            for p in pages
            if p.text or p.needs_ocr
        ]
    if ext in {".xlsx", ".xls"}:
        from mmi.ingest.excel import ExcelAdapter

        doc = ExcelAdapter().extract(path)
        return [
            Block(text=r.text_line, sheet=r.sheet, row=r.row)
            for r in doc.records
            if r.text_line.strip()
        ]
    if ext == ".pptx":
        from mmi.ingest.pptx import load_or_extract
        from mmi.ingest.pptx_normalize import section_aggregate_blocks, slides_to_blocks

        extract_dir = _resolve_extract_dir(path, extract_root)
        presentation = load_or_extract(
            path,
            extract_dir=extract_dir,
            document_key=document_key,
        )
        slide_blocks = slides_to_blocks(
            presentation,
            document_key=document_key,
            version_label=version_label,
            tipo=tipo,
        )
        section_blocks = section_aggregate_blocks(
            presentation,
            document_key=document_key,
            version_label=version_label,
            tipo=tipo,
        )
        return slide_blocks + section_blocks
    if ext in {".docx", ".doc"}:
        from mmi.ingest.docx import load_or_extract
        from mmi.ingest.docx_normalize import blocks_to_blocks, section_aggregate_blocks

        extract_dir = _resolve_extract_dir(path, extract_root)
        document = load_or_extract(
            path,
            extract_dir=extract_dir,
            document_key=document_key,
        )
        doc_blocks = blocks_to_blocks(
            document,
            document_key=document_key,
            version_label=version_label,
            tipo=tipo or "guia",
        )
        section_blocks = section_aggregate_blocks(
            document,
            document_key=document_key,
            version_label=version_label,
            tipo=tipo or "guia",
        )
        return doc_blocks + section_blocks
    raise ValueError(f"Formato no soportado para indexación: {ext} ({path})")
