"""Puerto OCR — factory y adapters."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mmi.config import get_ocr_settings
from mmi.ingest.ocr_azure import AzureDocumentIntelligenceAdapter
from mmi.ingest.ocr_models import OcrResult
from mmi.ingest.ocr_validate import validate_ocr_result
from mmi.ingest.ports import ExtractedDocument, OcrPort

if TYPE_CHECKING:
    from mmi.catalog.assets import CatalogAsset


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


def extract_with_ocr(
    path: Path,
    *,
    file_hash: str | None = None,
    validate: bool = True,
    catalog: dict[str, CatalogAsset] | None = None,
    document_key: str | None = None,
) -> ExtractedDocument:
    adapter = get_ocr_adapter()
    if isinstance(adapter, AzureDocumentIntelligenceAdapter):
        result = adapter.analyze(path, file_hash=file_hash)
        if validate:
            validations, quality = validate_ocr_result(
                result, catalog=catalog, document_key=document_key
            )
            result.quality = quality
            result.notes = list(result.notes) + [
                f"validaciones: {sum(1 for v in validations if v.status == 'review')} review"
            ]
            result.meta = {**result.meta, "validations": [v.to_dict() for v in validations]}
        return adapter.to_extracted_document(result)
    return adapter.extract(path)


def ocr_result_from_document(doc: ExtractedDocument, *, file_hash: str) -> OcrResult:
    from mmi.ingest.ocr_models import OcrBlock, OcrPage

    pages: list[OcrPage] = []
    for row in doc.meta.get("pages") or []:
        pages.append(
            OcrPage(
                page_number=int(row.get("page", 0)),
                text_raw=row.get("text_raw") or row.get("text") or "",
                text_normalized=row.get("text") or row.get("text_raw") or "",
                confidence=row.get("confidence"),
                status=row.get("status", "pass"),
                blocks=[OcrBlock.from_dict(b) for b in (row.get("blocks") or [])],
            )
        )
    return OcrResult(
        source_path=doc.source_path,
        file_hash=file_hash,
        engine=doc.meta.get("engine", "unknown"),
        engine_version=doc.meta.get("model_id", ""),
        model_id=doc.meta.get("model_id", ""),
        pages=pages,
        quality=doc.quality,
        notes=doc.notes,
        meta=doc.meta,
    )
