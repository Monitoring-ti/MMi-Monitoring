"""Índice de extracciones Fase 0 ya generadas (por directorio de salida)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


def slug_for_path(path: Path) -> str:
    return path.stem.replace(" ", "_")[:60]


def default_extract_roots(repo: Path | None = None) -> list[Path]:
    base = (repo or Path.cwd()) / "out"
    roots = [
        base / "lote1-extract",
        base / "docx-extract",
    ]
    if base.exists():
        for child in base.iterdir():
            if child.is_dir() and child.name.endswith("-extract") and child not in roots:
                roots.append(child)
    return roots


def _normalize_path(value: str | None) -> str:
    if not value:
        return ""
    return str(Path(value)).replace("/", "\\").lower()


def _counts_from_meta(fmt: str | None, meta: dict[str, Any], data: dict[str, Any]) -> tuple[int | None, int | None]:
    if fmt == "pptx":
        return (
            meta.get("slide_count") or data.get("slide_count"),
            meta.get("slides_pass") or data.get("slides_pass"),
        )
    if fmt == "docx":
        return (
            meta.get("block_count") or data.get("block_count"),
            meta.get("blocks_pass") or data.get("blocks_pass"),
        )
    if fmt in {"pdf", "ocr"} or data.get("pages"):
        pages = data.get("pages") or []
        sheets = meta.get("page_count") or len(pages)
        records = meta.get("pages_with_text")
        if records is None and pages:
            records = sum(1 for p in pages if (p.get("text") or p.get("text_raw")))
        return sheets, records
    sheets = len(data.get("sheets") or [])
    records = len(data.get("records") or [])
    return sheets or None, records or None


def load_extract_index(
    extract_roots: list[Path] | None = None,
    *,
    reviews_subdir: str | None = None,
) -> dict[str, Any]:
    """Índice de extracciones: by_source, by_slug y metadatos ligeros."""
    roots = extract_roots or default_extract_roots()
    by_source: dict[str, dict[str, Any]] = {}
    by_slug: dict[str, dict[str, Any]] = {}
    for root in roots:
        if not root.exists():
            continue
        subdir = reviews_subdir or root.name
        for child in root.iterdir():
            if not child.is_dir():
                continue
            meta_path = child / "extracted.json"
            if not meta_path.exists():
                continue
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            source = data.get("source_path") or ""
            key = _normalize_path(source)
            if not key:
                continue
            meta = data.get("meta") or {}
            fmt = data.get("format") or meta.get("format")
            quality = data.get("quality") or meta.get("quality") or "unknown"
            sheets, records = _counts_from_meta(fmt, meta, data)
            review_rel = f"{subdir}/{quote(child.name, safe='')}/review.html"
            entry = {
                "processed": True,
                "quality": quality,
                "format": fmt,
                "extract_dir": str(child),
                "file_hash": data.get("file_hash"),
                "notes": list(data.get("notes") or []),
                "sheets": sheets,
                "records": records,
                "extracted_at": datetime.fromtimestamp(
                    meta_path.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
                "review_url": review_rel if (child / "review.html").exists() else None,
            }
            by_source[key] = entry
            if source:
                by_slug[slug_for_path(Path(source))] = entry
            by_slug[child.name] = entry
    return {"by_source": by_source, "by_slug": by_slug}


def lookup_extract(
    absolute_path: str | None,
    index: dict[str, Any] | dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not absolute_path:
        return None
    if "by_source" in index:
        hit = index["by_source"].get(_normalize_path(absolute_path))
        if hit:
            return hit
        return index.get("by_slug", {}).get(slug_for_path(Path(absolute_path)))
    return index.get(_normalize_path(absolute_path))
