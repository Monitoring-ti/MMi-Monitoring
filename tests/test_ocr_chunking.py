"""Tests chunking y staging OCR C4 (sin red)."""

import json
from pathlib import Path

from mmi.index.ocr_chunking import chunk_ocr_pages
from mmi.index.ocr_store import load_ocr_staging, save_ocr_staging
from mmi.ingest.ocr_models import OcrBlock, OcrPage, OcrResult


def _sample_ocr() -> OcrResult:
    return OcrResult(
        source_path="/tmp/IFC-078.pdf",
        file_hash="deadbeef",
        engine="test",
        engine_version="1",
        model_id="test",
        pages=[
            OcrPage(
                page_number=1,
                text_raw="IFC-078 plano general",
                text_normalized="IFC-078 plano general",
                confidence=0.92,
                blocks=[
                    OcrBlock(
                        block_index=0,
                        block_type="paragraph",
                        text_raw="IFC-078 plano general",
                        text_normalized="IFC-078 plano general",
                        confidence=0.92,
                    )
                ],
            ),
            OcrPage(
                page_number=2,
                text_raw="",
                text_normalized="",
                confidence=0.40,
                blocks=[
                    OcrBlock(
                        block_index=0,
                        block_type="line",
                        text_raw="ruido",
                        text_normalized="ruido",
                        confidence=0.40,
                    )
                ],
            ),
        ],
    )


def test_chunk_ocr_pages_skips_low_confidence_block():
    chunks = chunk_ocr_pages(
        _sample_ocr().pages,
        document_name="IFC-078.pdf",
        document_key="IFC-078",
        version_label="REV15",
        tipo="plano",
    )
    assert len(chunks) == 1
    assert "IFC-078" in chunks[0].content
    assert chunks[0].page_start == 1


def test_save_and_load_ocr_staging(tmp_path: Path):
    ocr = _sample_ocr()
    root = save_ocr_staging(ocr, "IFC-078", tmp_path)
    assert (root / "manifest.json").exists()
    assert (root / "pages" / "1" / "ocr_result.json").exists()
    loaded = load_ocr_staging(root)
    assert loaded is not None
    assert loaded["page_count"] == 2
    assert len(loaded["pages_data"]) == 2
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["ocr_content_hash"]
