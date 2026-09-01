"""Construcción de process-manifest.json desde carpetas locales."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import re

from mmi.ingest.file_types import FILE_TYPES, phase0_for_extension
from mmi.tools.corpus_picker import scan_local_roots


def suggest_tipo(name: str, ext: str) -> str:
    n = name.lower()
    if ext in {".xlsx", ".xls", ".csv"}:
        return "tabla"
    if ext == ".pptx":
        return "presentacion"
    if ext == ".docx":
        return "guia"
    if "sop" in n or "procedimiento" in n or "progs" in n:
        return "sop"
    if "guia" in n or "guigs" in n:
        return "guia"
    if "norma" in n or "ncc" in n:
        return "norma"
    if "fmeca" in n or "rcm" in n:
        return "tabla"
    if "plano" in n or re.search(r"\d{3}[a-z]{2}-\d{5}", n, re.I):
        return "plano"
    if re.search(r"\bifc\b", n, re.I):
        return "sop"
    if ext == ".pdf":
        return "manual_oem"
    return "otro"


def build_full_corpus_manifest(
    corpus_root: Path,
    *,
    max_files: int = 10_000,
    include_only_ready: bool = True,
) -> dict:
    """Escanea corpus_root y arma manifest con archivos listos para Fase 0."""
    if not corpus_root.exists():
        return {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "lote": "ods1-full",
            "corpus_root": str(corpus_root),
            "count": 0,
            "local_ready": 0,
            "missing": [f"No existe carpeta: {corpus_root}"],
            "files": [],
        }

    root = corpus_root.resolve()
    items = scan_local_roots([root], max_files=max_files)
    files: list[dict] = []
    skipped = 0

    for it in items:
        if not it.absolute_path:
            continue
        ext = it.extension if it.extension.startswith(".") else f".{it.extension}"
        if ext == "(sin ext)":
            skipped += 1
            continue
        spec = FILE_TYPES.get(ext)
        if include_only_ready:
            if not spec or spec.status != "ready" or not spec.fase0_extract:
                skipped += 1
                continue
        elif not it.processable:
            skipped += 1
            continue

        phase0 = phase0_for_extension(ext) if spec else None
        files.append(
            {
                "id": it.id,
                "name": it.name,
                "relative_path": it.relative_path,
                "absolute_path": it.absolute_path,
                "source": it.source,
                "extension": ext,
                "ready": True,
                "include_in_analysis": True,
                "processed": it.processed,
                "process_quality": it.process_quality or None,
                "phase0": phase0,
                "document_key": "",
                "revision": "",
                "is_current": True,
                "suggested_tipo": suggest_tipo(it.name, ext),
            }
        )

    files.sort(key=lambda f: (f.get("relative_path") or "").lower())
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lote": "ods1-full",
        "corpus_root": str(root),
        "policy": "Todos los tipos ready en file_types.py; selección fina vía corpus_picker",
        "count": len(files),
        "skipped_non_ready": skipped,
        "local_ready": len(files),
        "online_only": 0,
        "missing": [],
        "files": files,
    }
