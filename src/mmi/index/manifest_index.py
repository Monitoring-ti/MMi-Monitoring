"""Selección de archivos indexables desde process-manifest.json."""

from __future__ import annotations

import json
from pathlib import Path

from mmi.analysis.status import _find_extract_dir
from mmi.catalog.logical_key import DocumentIdentityMeta, derive_logical_key

INDEXABLE_PHASE0 = frozenset({"excel", "pdf", "ocr", "pptx", "docx"})
REQUIRES_EXTRACT_PASS = frozenset({"excel", "ocr", "pptx", "docx"})


def derive_document_key(
    name: str,
    existing: str | None = None,
    entry: dict | None = None,
    *,
    tenant_slug: str = "monitoring",
) -> str:
    if existing and str(existing).strip():
        return str(existing).strip()
    payload = dict(entry or {})
    payload.setdefault("name", name)
    meta = DocumentIdentityMeta.from_manifest_entry(payload, tenant_slug=tenant_slug)
    return derive_logical_key(meta)


def indexable_from_manifest(
    manifest_path: Path,
    extract_root: Path,
    *,
    include_not_in_analysis: bool = False,
    tenant_slug: str = "monitoring",
) -> list[dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    indexable: list[dict] = []
    for entry in manifest.get("files") or []:
        if not include_not_in_analysis and entry.get("include_in_analysis") is False:
            continue
        abs_path = entry.get("absolute_path")
        if not abs_path or not Path(abs_path).exists():
            continue
        phase0 = entry.get("phase0", "")
        if phase0 not in INDEXABLE_PHASE0:
            continue

        extract_dir = _find_extract_dir(extract_root, abs_path)
        if extract_dir and (extract_dir / "extracted.json").exists():
            data = json.loads((extract_dir / "extracted.json").read_text(encoding="utf-8"))
            effective_quality = data.get("quality_override") or data.get("quality")
            if effective_quality != "pass":
                continue
        elif phase0 in REQUIRES_EXTRACT_PASS:
            continue

        name = entry.get("name") or Path(abs_path).name
        indexable.append(
            {
                "path": abs_path,
                "name": name,
                "tipo": entry.get("suggested_tipo", "otro"),
                "document_key": derive_document_key(
                    name,
                    entry.get("document_key"),
                    entry,
                    tenant_slug=tenant_slug,
                ),
                "version_label": entry.get("revision") or "",
                "is_current": entry.get("is_current", True),
                "phase0": phase0,
                "relative_path": entry.get("relative_path") or "",
                "origen": entry.get("source") or "ods1",
                "asset_tag": entry.get("asset_tag") or "",
                "modulo": entry.get("modulo") or "",
                "codigo_documento": entry.get("codigo_documento") or "",
            }
        )
    return indexable
