"""Puerto OCR — factory y adapters."""

from __future__ import annotations

from pathlib import Path

from mmi.config import get_ocr_settings
from mmi.ingest.ocr_azure import AzureDocumentIntelligenceAdapter
from mmi.ingest.ports import ExtractedDocument, OcrPort


class UnimplementedOcrAdapter(OcrPort):
    """Fallback cuando OCR_PROVIDER no está configurado."""

    def extract(self, path: Path) -> ExtractedDocument:
        return ExtractedDocument(
            markdown="",
            quality="reject",
            mime_type="application/pdf",
            source_path=str(path),
            notes=[
                "OCR no configurado. Define en .env:",
                "  MMI_OCR_PROVIDER=azure",
                "  AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://TU-RECURSO.cognitiveservices.azure.com/",
                "  AZURE_DOCUMENT_INTELLIGENCE_KEY=tu_clave",
                "Luego: python -m mmi.tools.ocr_test --check",
            ],
        )


def get_ocr_adapter() -> OcrPort:
    settings = get_ocr_settings()
    if settings.provider == "azure" and settings.azure_configured:
        return AzureDocumentIntelligenceAdapter(settings)
    return UnimplementedOcrAdapter()


def extract_with_ocr(path: Path, *, file_hash: str | None = None) -> ExtractedDocument:
    adapter = get_ocr_adapter()
    if isinstance(adapter, AzureDocumentIntelligenceAdapter):
        result = adapter.analyze(path, file_hash=file_hash)
        return adapter.to_extracted_document(result)
    return adapter.extract(path)
