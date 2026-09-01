"""Persistencia OCR — staging local + opcional Supabase (C4.8)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mmi.index.content_hash import content_hash
from mmi.ingest.ocr_models import OcrPage, OcrResult
from mmi.ingest.ocr_validate import OcrValidation


def staging_dir(out_root: Path, document_id: str) -> Path:
    safe = document_id.replace(" ", "_").replace("/", "-")[:80]
    return out_root / "ocr-staging" / safe


def save_page_json(page_dir: Path, page: OcrPage) -> Path:
    page_dir.mkdir(parents=True, exist_ok=True)
    path = page_dir / "ocr_result.json"
    path.write_text(json.dumps(page.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_page_json(page_dir: Path) -> OcrPage | None:
    path = page_dir / "ocr_result.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return OcrPage.from_dict(data)


def save_ocr_staging(
    ocr: OcrResult,
    document_id: str,
    out_root: Path,
    *,
    validations: list[OcrValidation] | None = None,
) -> Path:
    """Guarda resultado OCR en out/ocr-staging/{document_id}/."""
    root = staging_dir(out_root, document_id)
    root.mkdir(parents=True, exist_ok=True)

    for page in ocr.pages:
        page_dir = root / "pages" / str(page.page_number)
        save_page_json(page_dir, page)

    ocr_hash = content_hash(
        "\n".join(p.text_normalized or p.text_raw for p in ocr.pages)
    )
    manifest = {
        "document_id": document_id,
        "source_path": ocr.source_path,
        "file_hash": ocr.file_hash,
        "ocr_content_hash": ocr_hash,
        "engine": ocr.engine,
        "engine_version": ocr.engine_version,
        "model_id": ocr.model_id,
        "quality": ocr.quality,
        "page_count": ocr.page_count,
        "avg_confidence": ocr.avg_confidence,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "pages": [p.page_number for p in ocr.pages],
        "validations": [v.to_dict() for v in (validations or [])],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / "pages_index.json").write_text(
        json.dumps(ocr.pages_to_json(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return root


def load_ocr_staging(root: Path) -> dict[str, Any] | None:
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages: list[dict[str, Any]] = []
    pages_root = root / "pages"
    if pages_root.is_dir():
        for page_dir in sorted(pages_root.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 0):
            page = load_page_json(page_dir)
            if page:
                pages.append(page.to_dict())
    manifest["pages_data"] = pages
    return manifest


def page_already_processed(root: Path, page_number: int, page_hash: str) -> bool:
    page_dir = root / "pages" / str(page_number)
    page = load_page_json(page_dir)
    if page is None:
        return False
    return bool(page_hash and page.page_hash == page_hash)
