"""Tests sync OCR staging → extract dir."""

from __future__ import annotations

import json
from pathlib import Path

from mmi.index.ocr_sync import sync_ocr_to_extract


def test_sync_ocr_to_extract_writes_format_ocr(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    pages_dir = staging / "pages" / "1"
    pages_dir.mkdir(parents=True)
    (pages_dir / "ocr_result.json").write_text(
        json.dumps(
            {
                "page_number": 1,
                "text_raw": "TAG-001",
                "text_normalized": "TAG-001",
                "confidence": 0.95,
                "status": "pass",
                "blocks": [],
            }
        ),
        encoding="utf-8",
    )
    source = str((tmp_path / "plano.pdf").resolve())
    (staging / "manifest.json").write_text(
        json.dumps(
            {
                "document_id": "PLAN-1",
                "source_path": source,
                "file_hash": "abc",
                "engine": "azure",
                "page_count": 1,
                "avg_confidence": 0.95,
                "quality": "pass",
            }
        ),
        encoding="utf-8",
    )
    extract_root = tmp_path / "extract"
    out = sync_ocr_to_extract(staging, extract_root)
    data = json.loads((out / "extracted.json").read_text(encoding="utf-8"))
    assert data["format"] == "ocr"
    assert data["source_path"] == source
    assert len(data["pages"]) == 1
    assert data["pages"][0]["text"] == "TAG-001"
