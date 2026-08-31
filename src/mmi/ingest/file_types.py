"""Registro central de tipos de archivo MMI — Fase 0, indexación y chunking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["ready", "partial", "planned", "unsupported", "reject_only"]


@dataclass(frozen=True)
class FileTypeSpec:
    extension: str
    label: str
    phase0: str | None
    status: Status
    fase0_extract: bool
    index: bool
    chunking: str | None
    extraction_method: str | None
    spec_doc: str | None = None
    notes: str = ""

    @property
    def processable_ui(self) -> bool:
        """Marcado procesable en corpus-picker (puede ser aspiracional)."""
        return self.status in {"ready", "partial", "planned"}


FILE_TYPES: dict[str, FileTypeSpec] = {
    ".pdf": FileTypeSpec(
        extension=".pdf",
        label="PDF (texto nativo)",
        phase0="pdf",
        status="ready",
        fase0_extract=True,
        index=True,
        chunking="chunk_pdf_blocks",
        extraction_method="native",
        notes="pdfplumber; páginas sin texto → candidata OCR",
    ),
    ".xlsx": FileTypeSpec(
        extension=".xlsx",
        label="Excel",
        phase0="excel",
        status="ready",
        fase0_extract=True,
        index=True,
        chunking="chunk_xlsx_blocks",
        extraction_method="tabular",
        notes="openpyxl; filas citables sheet/row",
    ),
    ".xls": FileTypeSpec(
        extension=".xls",
        label="Excel legacy",
        phase0="excel",
        status="partial",
        fase0_extract=False,
        index=False,
        chunking="chunk_xlsx_blocks",
        extraction_method="tabular",
        notes="openpyxl puede fallar; convertir a xlsx recomendado",
    ),
    ".pptx": FileTypeSpec(
        extension=".pptx",
        label="PowerPoint",
        phase0="pptx",
        status="ready",
        fase0_extract=True,
        index=True,
        chunking="chunk_pptx_blocks",
        extraction_method="slide",
        spec_doc="docs/plan-pptx-extraction.md",
        notes="Jerárquico slide→elemento; FMECA/RCM lote 1 OK",
    ),
    ".docx": FileTypeSpec(
        extension=".docx",
        label="Word (OOXML)",
        phase0="docx",
        status="ready",
        fase0_extract=True,
        index=True,
        chunking="chunk_docx_blocks",
        extraction_method="structured",
        spec_doc="docs/plan-docx-extraction.md",
        notes="Jerárquico sección→bloque; ~20 archivos en corpus",
    ),
    ".doc": FileTypeSpec(
        extension=".doc",
        label="Word legacy (binary)",
        phase0="doc",
        status="partial",
        fase0_extract=True,
        index=True,
        chunking="chunk_docx_blocks",
        extraction_method="structured",
        spec_doc="docs/plan-docx-extraction.md",
        notes="Requiere conversión DOC→DOCX (LibreOffice) antes de extraer",
    ),
    ".ocr": FileTypeSpec(
        extension=".pdf",
        label="PDF escaneado / plano",
        phase0="ocr",
        status="ready",
        fase0_extract=True,
        index=True,
        chunking="chunk_pdf_blocks + contexto OCR",
        extraction_method="ocr",
        spec_doc="docs/plan-fase-c-ocr.md",
        notes="Azure Document Intelligence; IFC-078 piloto OK",
    ),
    ".csv": FileTypeSpec(
        extension=".csv",
        label="CSV",
        phase0="excel",
        status="planned",
        fase0_extract=False,
        index=False,
        chunking="chunk_xlsx_blocks",
        extraction_method="tabular",
        notes="En PROCESSABLE del picker; sin adapter dedicado",
    ),
    ".txt": FileTypeSpec(
        extension=".txt",
        label="Texto plano",
        phase0="text",
        status="unsupported",
        fase0_extract=False,
        index=False,
        chunking=None,
        extraction_method="native",
        notes="Baja prioridad MVP",
    ),
    ".md": FileTypeSpec(
        extension=".md",
        label="Markdown",
        phase0="text",
        status="unsupported",
        fase0_extract=False,
        index=False,
        chunking=None,
        extraction_method="native",
        notes="Docs internos del repo",
    ),
    ".jpg": FileTypeSpec(
        extension=".jpg",
        label="Imagen JPEG",
        phase0="ocr",
        status="planned",
        fase0_extract=False,
        index=False,
        chunking=None,
        extraction_method="ocr",
        spec_doc="docs/plan-fase-c-ocr.md",
        notes="6 en corpus; OCR selectivo por región",
    ),
    ".jpeg": FileTypeSpec(
        extension=".jpeg",
        label="Imagen JPEG",
        phase0="ocr",
        status="planned",
        fase0_extract=False,
        index=False,
        chunking=None,
        extraction_method="ocr",
        spec_doc="docs/plan-fase-c-ocr.md",
        notes="Alias .jpg",
    ),
    ".png": FileTypeSpec(
        extension=".png",
        label="Imagen PNG",
        phase0="ocr",
        status="planned",
        fase0_extract=False,
        index=False,
        chunking=None,
        extraction_method="ocr",
        spec_doc="docs/plan-fase-c-ocr.md",
        notes="Diagramas / capturas",
    ),
    ".tif": FileTypeSpec(
        extension=".tif",
        label="TIFF",
        phase0="ocr",
        status="planned",
        fase0_extract=False,
        index=False,
        chunking=None,
        extraction_method="ocr",
        notes="Planos escaneados multipágina",
    ),
    ".tiff": FileTypeSpec(
        extension=".tiff",
        label="TIFF",
        phase0="ocr",
        status="planned",
        fase0_extract=False,
        index=False,
        chunking=None,
        extraction_method="ocr",
        notes="Alias .tif",
    ),
}


def spec_for_path(path: str) -> FileTypeSpec | None:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    key = f".{ext}" if ext else ""
    return FILE_TYPES.get(key)


def phase0_for_extension(ext: str) -> str | None:
    ext = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
    spec = FILE_TYPES.get(ext)
    return spec.phase0 if spec else None


def list_by_status(status: Status) -> list[FileTypeSpec]:
    return [s for s in FILE_TYPES.values() if s.status == status]
