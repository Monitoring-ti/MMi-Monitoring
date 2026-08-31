from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


Quality = Literal["pass", "review", "reject"]


@dataclass(frozen=True)
class CitationAnchor:
    """Dónde citar en el original: página OCR o celda Excel."""

    page_number: int | None = None
    sheet: str | None = None
    row: int | None = None
    column: str | None = None


@dataclass(frozen=True)
class SpreadsheetRecord:
    """Una fila de datos extraída, lista para citar e indexar."""

    sheet: str
    row: int  # 1-based, número de fila en Excel
    values: dict[str, str | None]
    text_line: str


@dataclass
class SheetSummary:
    name: str
    header_row: int | None
    data_rows: int
    columns: list[str]
    status: Literal["ok", "empty", "no_header", "template_only"]


@dataclass
class ExtractedDocument:
    markdown: str
    quality: Quality
    mime_type: str
    source_path: str
    anchors: list[CitationAnchor] = field(default_factory=list)
    ocr_confidence: float | None = None
    notes: list[str] = field(default_factory=list)
    records: list[SpreadsheetRecord] = field(default_factory=list)
    sheets: list[SheetSummary] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


class StoragePort(ABC):
    @abstractmethod
    def fetch(self, uri: str) -> Path:
        """Baja el binario y devuelve una ruta local temporal."""


class SpreadsheetPort(ABC):
    @abstractmethod
    def extract(self, path: Path) -> ExtractedDocument:
        """XLSX/CSV → Markdown tabular + anclas sheet/row. Nunca OCR."""


class PresentationPort(ABC):
    @abstractmethod
    def extract(self, path: Path) -> ExtractedDocument:
        """PPTX → slides estructurados + Markdown resumen."""


class OcrPort(ABC):
    @abstractmethod
    def extract(self, path: Path) -> ExtractedDocument:
        """PDF imagen/híbrido → Markdown paginado + confianza."""
