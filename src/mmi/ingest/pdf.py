"""Extractor PDF: texto nativo página a página con pdfplumber."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mmi.ingest.ports import CitationAnchor, ExtractedDocument


@dataclass(frozen=True)
class PageBlock:
    page: int
    text: str
    needs_ocr: bool
    char_count: int


class PdfAdapter:
    """Extrae texto nativo. Páginas sin capa de texto quedan marcadas needs_ocr."""

    def extract(self, path: Path) -> ExtractedDocument:
        pages = self._read_pages(path)
        return self._build_document(path, pages)

    def extract_hybrid(self, path: Path) -> ExtractedDocument:
        """Texto nativo donde hay capa; OCR para páginas sin texto (C4.9)."""
        pages = self._read_pages(path)
        needs_ocr = [p for p in pages if p.needs_ocr]
        if not needs_ocr:
            return self._build_document(path, pages)
        if len(needs_ocr) == len(pages):
            from mmi.ingest.ocr import extract_with_ocr

            return extract_with_ocr(path)

        from mmi.ingest.ocr import extract_with_ocr

        ocr_doc = extract_with_ocr(path)
        ocr_by_page = {int(p.get("page", 0)): p for p in (ocr_doc.meta.get("pages") or [])}

        merged_pages: list[PageBlock] = []
        notes: list[str] = [f"Híbrido: {len(needs_ocr)}/{len(pages)} páginas vía OCR"]
        for block in pages:
            if block.needs_ocr:
                ocr_page = ocr_by_page.get(block.page, {})
                text = (ocr_page.get("text") or ocr_page.get("text_raw") or "").strip()
                merged_pages.append(
                    PageBlock(
                        page=block.page,
                        text=text,
                        needs_ocr=False,
                        char_count=len(text),
                    )
                )
            else:
                merged_pages.append(block)

        doc = self._build_document(path, merged_pages)
        return ExtractedDocument(
            markdown=doc.markdown,
            quality=ocr_doc.quality if ocr_doc.quality != "pass" else doc.quality,
            mime_type=doc.mime_type,
            source_path=doc.source_path,
            anchors=doc.anchors,
            ocr_confidence=ocr_doc.ocr_confidence,
            notes=notes + doc.notes,
            meta={
                **doc.meta,
                "format": "pdf_hybrid",
                "ocr_pages": [p.page for p in needs_ocr],
                "ocr_confidence": ocr_doc.ocr_confidence,
                "engine": ocr_doc.meta.get("engine"),
            },
        )

    @staticmethod
    def _read_pages(path: Path) -> list[PageBlock]:
        import pdfplumber

        pages: list[PageBlock] = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "").strip()
                pages.append(
                    PageBlock(
                        page=i,
                        text=text,
                        needs_ocr=not bool(text),
                        char_count=len(text),
                    )
                )
        return pages

    def _build_document(self, path: Path, pages: list[PageBlock]) -> ExtractedDocument:
        notes: list[str] = []
        anchors: list[CitationAnchor] = []
        parts: list[str] = [f"# {path.name}", ""]

        for block in pages:
            anchors.append(CitationAnchor(page_number=block.page))
            if block.text:
                parts.append(f"## Página {block.page}")
                parts.append("")
                preview = (
                    block.text
                    if len(block.text) <= 4000
                    else block.text[:4000] + "\n\n_… texto truncado en MD (ver JSON/revisión)_"
                )
                parts.append(preview)
                parts.append("")
            else:
                notes.append(f"Página {block.page}: sin texto nativo (candidata OCR)")

        total = len(pages)
        with_text = sum(1 for p in pages if not p.needs_ocr)
        ocr_pages = total - with_text
        chars = sum(p.char_count for p in pages)

        if total == 0 or with_text == 0:
            quality = "reject"
            if total == 0:
                notes.append("PDF sin páginas")
        elif ocr_pages > 0:
            ratio = ocr_pages / total
            quality = "review" if ratio > 0.05 else "pass"
            notes.append(f"{ocr_pages}/{total} páginas sin texto nativo")
        else:
            quality = "pass"

        return ExtractedDocument(
            markdown="\n".join(parts).strip() + "\n",
            quality=quality,
            mime_type="application/pdf",
            source_path=str(path),
            anchors=anchors,
            notes=notes,
            meta={
                "format": "pdf",
                "file_name": path.name,
                "page_count": total,
                "pages_with_text": with_text,
                "pages_needs_ocr": ocr_pages,
                "char_count": chars,
                "quality": quality,
                "pages": pages_to_json(pages),
            },
        )


def pages_to_json(pages: list[PageBlock]) -> list[dict]:
    return [
        {
            "page": p.page,
            "char_count": p.char_count,
            "needs_ocr": p.needs_ocr,
            "text": p.text,
        }
        for p in pages
    ]
