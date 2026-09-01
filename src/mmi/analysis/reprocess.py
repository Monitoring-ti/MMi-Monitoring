"""Acciones sobre documentos rechazados, con error o pendientes de repaso."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mmi.analysis.llm_review import review_extraction
from mmi.analysis.status import collect_analysis_status
from mmi.corpus.paths import DEFAULT_EXTRACT_FULL
from mmi.index.chunking import file_sha256
from mmi.index.manifest_index import derive_document_key, indexable_from_manifest
from mmi.index.pipeline import ingest_file
from mmi.index.store import (
    pg_delete_chunks,
    pg_delete_document,
    pg_find_document,
    pg_get_tenant_id,
    qdrant_delete_document_points,
)


def find_manifest_entry(manifest_path: Path, name: str) -> dict[str, Any] | None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name_lower = name.strip().lower()
    for entry in manifest.get("files") or []:
        if (entry.get("name") or "").lower() == name_lower:
            return entry
    return None


def set_manifest_flag(
    manifest_path: Path,
    name: str,
    *,
    include_in_analysis: bool | None = None,
) -> bool:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    found = False
    name_lower = name.strip().lower()
    for entry in manifest.get("files") or []:
        if (entry.get("name") or "").lower() != name_lower:
            continue
        if include_in_analysis is not None:
            entry["include_in_analysis"] = include_in_analysis
        found = True
    if found:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return found


def delete_extract_dir(extract_dir: Path) -> bool:
    if extract_dir.exists() and extract_dir.is_dir():
        shutil.rmtree(extract_dir)
        return True
    return False


def apply_quality_override(
    extract_dir: Path,
    quality: str,
    *,
    note: str = "",
    source: str = "manual",
) -> dict[str, Any]:
    meta_path = extract_dir / "extracted.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"No hay extracción en {extract_dir}")
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    data["quality_override"] = quality
    data["quality"] = quality
    notes = list(data.get("notes") or [])
    if note:
        notes.append(f"[{source}] {note}")
    data["notes"] = notes
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"quality": quality, "extract_dir": str(extract_dir)}


def clear_index_for_path(path: Path, tenant_slug: str = "monitoring") -> dict[str, Any]:
    if not path.exists():
        return {"cleared": False, "reason": "archivo no existe"}
    try:
        tenant_id = pg_get_tenant_id(tenant_slug)
    except RuntimeError as exc:
        return {"cleared": False, "reason": str(exc)}
    try:
        file_hash = file_sha256(path)
        existing = pg_find_document(tenant_id, file_hash)
        if not existing:
            return {"cleared": False, "reason": "sin fila en índice"}
        doc_id = existing[0]["id"]
        qdrant_delete_document_points(tenant_id, doc_id)
        pg_delete_chunks(doc_id)
        pg_delete_document(doc_id)
        return {"cleared": True, "document_id": doc_id}
    except Exception as exc:  # noqa: BLE001
        return {"cleared": False, "reason": str(exc)[:200]}


def reprocess_phase0(
    name: str,
    *,
    manifest_path: Path,
    extract_root: Path,
    force: bool = True,
) -> dict[str, Any]:
    from mmi.tools.process_manifest import process_phase0_files

    entry = find_manifest_entry(manifest_path, name)
    if not entry:
        return {"ok": False, "error": f"No está en manifest: {name}"}
    abs_path = entry.get("absolute_path")
    if not abs_path or not Path(abs_path).exists():
        return {"ok": False, "error": "Archivo no encontrado en disco"}
    manifest = {"files": [entry]}
    results = process_phase0_files(manifest, extract_root, force=force)
    row = results[0] if results else {}
    return {
        "ok": row.get("quality") not in {"error", "missing"} and row.get("quality") != "missing",
        "result": row,
    }


def reprocess_index(
    name: str,
    *,
    manifest_path: Path,
    extract_root: Path,
    tenant_slug: str = "monitoring",
    delete_failed: bool = True,
) -> dict[str, Any]:
    entry = find_manifest_entry(manifest_path, name)
    if not entry:
        return {"ok": False, "error": f"No está en manifest: {name}"}
    path = Path(entry["absolute_path"])
    if not path.exists():
        return {"ok": False, "error": "Archivo no encontrado en disco"}
    if delete_failed:
        clear_index_for_path(path, tenant_slug)
    try:
        res = ingest_file(
            path,
            tenant_slug=tenant_slug,
            tipo=entry.get("suggested_tipo", "otro"),
            version_label=entry.get("revision") or None,
            document_key=derive_document_key(name, entry.get("document_key")),
            activate=True,
        )
        if res.get("archivo"):
            from mmi.index.summary_sync import patch_index_summary_row

            patch_index_summary_row(manifest_path.parent / "index-corpus-summary.json", res)
        return {"ok": res.get("estado") in {"active", "indexed", "indexado"}, "result": res}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300]}


def run_ingestion_action(
    action: str,
    names: list[str],
    *,
    out_dir: Path,
    manifest_path: Path | None = None,
    extract_root: Path | None = None,
    tenant_slug: str = "monitoring",
    force: bool = True,
    quality: str | None = None,
    model: str | None = None,
    delete_failed: bool = True,
    note: str = "",
) -> dict[str, Any]:
    manifest_path = manifest_path or out_dir / "process-manifest.json"
    extract_root = extract_root or DEFAULT_EXTRACT_FULL
    results: list[dict[str, Any]] = []

    for name in names:
        name = name.strip()
        if not name:
            continue
        try:
            if action == "exclude":
                ok = set_manifest_flag(manifest_path, name, include_in_analysis=False)
                if not ok:
                    results.append({"name": name, "ok": False, "error": "no en manifest", "action": action})
                    continue
                results.append({"name": name, "ok": True, "action": action, "new_status": "excluido"})
            elif action == "mark_not_relevant":
                note_text = note or "No relevante: plantilla vacía / solo encabezados Excel"
                ok = set_manifest_flag(manifest_path, name, include_in_analysis=False)
                if not ok:
                    results.append({"name": name, "ok": False, "error": "no en manifest", "action": action})
                    continue
                entry = find_manifest_entry(manifest_path, name)
                index_cleared: dict[str, Any] | None = None
                if entry and entry.get("absolute_path"):
                    index_cleared = clear_index_for_path(Path(entry["absolute_path"]), tenant_slug)
                from mmi.analysis.extract_index import lookup_extract, load_extract_index

                hit = lookup_extract((entry or {}).get("absolute_path"), load_extract_index()) if entry else None
                if hit and hit.get("extract_dir"):
                    apply_quality_override(
                        Path(hit["extract_dir"]),
                        "reject",
                        note=note_text,
                        source="dashboard",
                    )
                results.append({
                    "name": name,
                    "ok": True,
                    "action": action,
                    "note": note_text,
                    "index_cleared": index_cleared,
                    "new_status": "excluido",
                })
            elif action == "mark_verify":
                note_text = note or "Verificar: posible foto escaneada o texto manuscrito (OCR)"
                entry = find_manifest_entry(manifest_path, name)
                if not entry:
                    results.append({"name": name, "ok": False, "error": "no en manifest"})
                    continue
                from mmi.analysis.extract_index import lookup_extract, load_extract_index

                hit = lookup_extract(entry.get("absolute_path"), load_extract_index())
                if not hit or not hit.get("extract_dir"):
                    results.append({"name": name, "ok": False, "error": "sin extracción"})
                    continue
                apply_quality_override(
                    Path(hit["extract_dir"]),
                    "review",
                    note=note_text,
                    source="dashboard",
                )
                results.append({
                    "name": name,
                    "ok": True,
                    "quality": "review",
                    "action": action,
                    "note": note_text,
                    "new_status": "review",
                })
            elif action == "include":
                ok = set_manifest_flag(manifest_path, name, include_in_analysis=True)
                results.append({"name": name, "ok": ok, "action": action})
            elif action == "delete_extract":
                entry = find_manifest_entry(manifest_path, name)
                extract_dir = None
                if entry:
                    from mmi.analysis.extract_index import lookup_extract, load_extract_index

                    hit = lookup_extract(entry.get("absolute_path"), load_extract_index())
                    if hit:
                        extract_dir = Path(hit["extract_dir"])
                deleted = delete_extract_dir(extract_dir) if extract_dir else False
                results.append({"name": name, "ok": deleted, "action": action})
            elif action == "reextract":
                r = reprocess_phase0(
                    name,
                    manifest_path=manifest_path,
                    extract_root=extract_root,
                    force=force,
                )
                results.append({"name": name, **r, "action": action})
            elif action == "reindex":
                r = reprocess_index(
                    name,
                    manifest_path=manifest_path,
                    extract_root=extract_root,
                    tenant_slug=tenant_slug,
                    delete_failed=delete_failed,
                )
                results.append({"name": name, **r, "action": action})
            elif action == "apply_quality":
                entry = find_manifest_entry(manifest_path, name)
                if not entry:
                    results.append({"name": name, "ok": False, "error": "no en manifest"})
                    continue
                from mmi.analysis.extract_index import lookup_extract, load_extract_index

                hit = lookup_extract(entry.get("absolute_path"), load_extract_index())
                if not hit or not hit.get("extract_dir"):
                    results.append({"name": name, "ok": False, "error": "sin extracción"})
                    continue
                q = quality or "review"
                apply_quality_override(
                    Path(hit["extract_dir"]),
                    q,
                    note=note or f"override → {q}",
                    source="dashboard",
                )
                results.append({"name": name, "ok": True, "quality": q, "action": action})
            elif action == "ai_review":
                entry = find_manifest_entry(manifest_path, name)
                if not entry:
                    results.append({"name": name, "ok": False, "error": "no en manifest"})
                    continue
                from mmi.analysis.extract_index import lookup_extract, load_extract_index

                hit = lookup_extract(entry.get("absolute_path"), load_extract_index())
                if not hit or not hit.get("extract_dir"):
                    r = reprocess_phase0(
                        name,
                        manifest_path=manifest_path,
                        extract_root=extract_root,
                        force=True,
                    )
                    if not r.get("ok"):
                        results.append({"name": name, "ok": False, "error": "sin extracción", **r})
                        continue
                    hit = lookup_extract(entry.get("absolute_path"), load_extract_index())
                idx_row = _index_error_for_name(out_dir, name)
                review = review_extraction(
                    Path(hit["extract_dir"]),
                    document_name=name,
                    index_error=(idx_row or {}).get("detalle"),
                    model=model,
                )
                results.append({"name": name, "action": action, **review})
            else:
                results.append({"name": name, "ok": False, "error": f"acción desconocida: {action}"})
        except Exception as exc:  # noqa: BLE001
            results.append({"name": name, "ok": False, "error": str(exc)[:300], "action": action})

    refresh_dashboard(manifest_path, extract_root, out_dir)
    ok_count = sum(1 for r in results if r.get("ok"))
    summary: dict[str, Any] = {}
    try:
        summary = json.loads((out_dir / "analysis-status.json").read_text(encoding="utf-8")).get(
            "summary", {}
        )
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "action": action,
        "total": len(results),
        "ok": ok_count,
        "results": results,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _index_error_for_name(out_dir: Path, name: str) -> dict[str, Any] | None:
    path = out_dir / "index-corpus-summary.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for row in reversed(data.get("results") or []):
        if row.get("archivo") == name and row.get("estado") == "error":
            return row
    return None


def refresh_dashboard(
    manifest_path: Path,
    extract_root: Path,
    out_dir: Path,
) -> dict[str, Any]:
    import importlib

    from mmi.analysis import status as status_mod

    from mmi.analysis.review_shell import write_review_dashboard

    importlib.reload(status_mod)
    payload = status_mod.collect_analysis_status(manifest_path, extract_root, out_dir=out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_review_dashboard(out_dir, payload)
    return payload


def list_actionable(out_dir: Path) -> dict[str, Any]:
    manifest_path = out_dir / "process-manifest.json"
    extract_root = DEFAULT_EXTRACT_FULL
    if not manifest_path.exists():
        return {"reject": [], "error": [], "index_error": []}
    payload = collect_analysis_status(manifest_path, extract_root, out_dir=out_dir)
    reject, fase0_err, index_err = [], [], []
    for a in payload.get("analyses") or []:
        name = a.get("name")
        if not name:
            continue
        st = a.get("status")
        q = a.get("quality")
        if st in {"reject", "review"} or q == "error":
            reject.append(name)
        if q == "error" or st == "reject":
            fase0_err.append(name)
        if a.get("index_status") == "error":
            index_err.append(name)
    return {
        "reject_or_review": reject,
        "fase0_problem": fase0_err,
        "index_error": index_err,
        "indexable_pending": indexable_from_manifest(manifest_path, extract_root)[:20],
    }
