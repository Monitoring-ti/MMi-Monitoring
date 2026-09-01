"""Dashboard estado OCR staging (C4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def scan_ocr_staging(out_root: Path = Path("out")) -> list[dict[str, Any]]:
    root = out_root / "ocr-staging"
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        manifest_path = child / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.append(
            {
                "document_id": data.get("document_id") or child.name,
                "quality": data.get("quality"),
                "page_count": data.get("page_count"),
                "avg_confidence": data.get("avg_confidence"),
                "engine": data.get("engine"),
                "staging_path": str(child),
                "review_url": "ocr-review.html"
                if (child / "ocr-review.html").exists()
                else None,
                "validations": data.get("validations") or [],
            }
        )
    return rows


def ocr_staging_summary(out_root: Path = Path("out")) -> dict[str, Any]:
    rows = scan_ocr_staging(out_root)
    return {
        "count": len(rows),
        "pass": sum(1 for r in rows if r.get("quality") == "pass"),
        "review": sum(1 for r in rows if r.get("quality") == "review"),
        "reject": sum(1 for r in rows if r.get("quality") == "reject"),
        "documents": rows,
    }
