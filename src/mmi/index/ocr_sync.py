"""Sincroniza staging OCR → carpeta Fase 0 (extracted.json) para indexación."""

from __future__ import annotations

import json
from pathlib import Path

from mmi.analysis.extract_index import slug_for_path


def sync_ocr_to_extract(
    staging_path: Path,
    extract_root: Path,
    *,
    slug: str | None = None,
) -> Path:
    """Escribe extracted.json desde manifest + pages_index en extract_root."""
    staging_path = Path(staging_path)
    manifest_path = staging_path / "manifest.json"
    pages_path = staging_path / "pages_index.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Sin manifest en {staging_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages = []
    if pages_path.exists():
        pages = json.loads(pages_path.read_text(encoding="utf-8"))
    else:
        pages_root = staging_path / "pages"
        for page_dir in sorted(pages_root.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 0):
            page_file = page_dir / "ocr_result.json"
            if page_file.exists():
                pages.append(json.loads(page_file.read_text(encoding="utf-8")))

    source = manifest.get("source_path") or ""
    source_abs = str(Path(source).resolve()) if source else ""
    name = Path(source).name if source else manifest.get("document_id", "ocr")
    slug = slug or slug_for_path(Path(name))
    target = extract_root / slug
    target.mkdir(parents=True, exist_ok=True)

    pages_out = []
    for row in pages:
        page_num = int(row.get("page_number") or row.get("page") or 0)
        pages_out.append(
            {
                "page": page_num,
                "text": row.get("text_normalized") or row.get("text") or row.get("text_raw") or "",
                "text_raw": row.get("text_raw") or "",
                "confidence": row.get("confidence"),
                "status": row.get("status", "pass"),
                "needs_ocr": False,
                "char_count": len(row.get("text_raw") or ""),
                "blocks": row.get("blocks") or [],
            }
        )

    quality = manifest.get("quality") or "review"
    payload = {
        "format": "ocr",
        "source_path": source_abs or source,
        "file_hash": manifest.get("file_hash"),
        "quality": quality,
        "notes": [f"OCR staging {manifest.get('engine', '')}"],
        "ocr_confidence": manifest.get("avg_confidence"),
        "meta": {
            "format": "ocr",
            "engine": manifest.get("engine"),
            "model_id": manifest.get("model_id"),
            "file_name": name,
            "page_count": manifest.get("page_count", len(pages_out)),
            "pages_with_text": sum(1 for p in pages_out if (p.get("text") or "").strip()),
            "avg_confidence": manifest.get("avg_confidence"),
            "plan_detection": manifest.get("plan_detection"),
            "ocr_staging": str(staging_path),
        },
        "pages": pages_out,
        "ocr_result_file": "ocr_result.json",
    }
    (target / "extracted.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_parts = [f"# {name}", ""]
    for pg in pages_out[:30]:
        md_parts.append(f"## Página {pg['page']}")
        md_parts.append("")
        md_parts.append((pg.get("text") or "")[:3000])
        md_parts.append("")
    (target / "extracted.md").write_text("\n".join(md_parts), encoding="utf-8")
    (target / "ocr_result.json").write_text(
        json.dumps(pages_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target
