"""Sincroniza index-corpus-summary.json con Postgres (fuente de verdad post reprocess)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mmi.index.chunking import file_sha256
from mmi.index.store import pg_count_chunks, pg_get_tenant_id, pg_list_documents


def _stats(results: list[dict]) -> dict[str, int]:
    ok = [r for r in results if r.get("estado") in {"active", "indexed", "indexado"}]
    dup = [r for r in results if r.get("estado") == "duplicado"]
    same = [r for r in results if r.get("estado") == "mismo_contenido"]
    review = [r for r in results if r.get("estado") == "needs_review"]
    err = [r for r in results if r.get("estado") == "error"]
    return {
        "total": len(results),
        "indexados": len(ok),
        "chunks": sum(int(r.get("chunks") or 0) for r in ok),
        "tokens": sum(int(r.get("tokens") or 0) for r in ok),
        "duplicados": len(dup),
        "mismo_contenido": len(same),
        "needs_review": len(review),
        "errores": len(err),
    }


def _load_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"results": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"results": []}


def _row_from_doc(name: str, doc: dict, *, chunks: int, canonical: bool) -> dict[str, Any]:
    fh = doc.get("file_hash") or ""
    if canonical and chunks > 0 and doc.get("status") in {"active", "indexed"}:
        estado = "active" if doc.get("status") == "active" else "indexed"
        return {
            "archivo": name,
            "estado": estado,
            "document_id": doc.get("id"),
            "catalog_id": doc.get("catalog_id"),
            "document_key": doc.get("document_key"),
            "chunks": chunks,
            "sha256": fh[:12] if fh else None,
        }
    return {
        "archivo": name,
        "estado": "duplicado",
        "document_id": doc.get("id"),
        "document_key": doc.get("document_key"),
        "chunks": 0,
        "sha256": fh[:12] if fh else None,
    }


def sync_index_summary(
    manifest_path: Path,
    summary_path: Path,
    *,
    tenant_slug: str = "monitoring",
) -> dict[str, Any]:
    """Reconcilia summary JSON con documentos en Postgres (por file_hash)."""
    tenant_id = pg_get_tenant_id(tenant_slug)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prior = _load_summary(summary_path)
    prior_by_name = {r["archivo"]: r for r in prior.get("results") or [] if r.get("archivo")}

    docs = pg_list_documents(
        tenant_id,
        select="id,titulo,file_hash,document_key,catalog_id,status,is_current",
    )
    by_hash: dict[str, dict] = {}
    for doc in docs:
        fh = doc.get("file_hash")
        if fh and fh not in by_hash:
            by_hash[fh] = doc

    chunk_cache: dict[str, int] = {}
    canonical_hash: set[str] = set()
    pending: list[tuple[str, str, dict]] = []

    for entry in manifest.get("files") or []:
        if entry.get("include_in_analysis") is False:
            continue
        name = entry.get("name") or ""
        abs_path = entry.get("absolute_path")
        if not name or not abs_path:
            continue
        path = Path(abs_path)
        if not path.is_file():
            continue
        fh = file_sha256(path)
        doc = by_hash.get(fh)
        if not doc:
            continue
        doc_id = doc["id"]
        if doc_id not in chunk_cache:
            chunk_cache[doc_id] = pg_count_chunks(doc_id)
        pending.append((name, fh, doc))

    for _name, fh, doc in pending:
        chunks = chunk_cache.get(doc["id"], 0)
        if chunks > 0 and doc.get("status") in {"active", "indexed"}:
            canonical_hash.add(fh)

    results_by_name: dict[str, dict] = dict(prior_by_name)
    updated = 0
    for name, fh, doc in pending:
        chunks = chunk_cache.get(doc["id"], 0)
        row = _row_from_doc(name, doc, chunks=chunks, canonical=fh in canonical_hash)
        if results_by_name.get(name) != row:
            updated += 1
        results_by_name[name] = row

    results = list(results_by_name.values())
    meta = {
        "manifest": str(manifest_path.resolve()),
        "synced_from": "postgres",
        "tenant": tenant_slug,
        "progress": f"{len(results)}/{len(results)}",
    }
    if prior.get("extract_dir"):
        meta["extract_dir"] = prior["extract_dir"]
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **meta,
        "results": results,
        "stats": _stats(results),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"updated_rows": updated, "stats": payload["stats"], "path": str(summary_path)}


def patch_index_summary_row(summary_path: Path, result: dict[str, Any]) -> None:
    """Actualiza o añade una fila tras reprocess_index / ingest_file."""
    name = result.get("archivo")
    if not name:
        return
    prior = _load_summary(summary_path)
    rows = [r for r in prior.get("results") or [] if r.get("archivo") != name]
    rows.append(result)
    meta = {k: v for k, v in prior.items() if k not in {"results", "stats", "updated_at"}}
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **meta,
        "results": rows,
        "stats": _stats(rows),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
