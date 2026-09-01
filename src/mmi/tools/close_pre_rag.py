"""Cierra pendientes pre-validación RAG: triaje Fase 0 review + exclusiones."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from mmi.analysis.extract_index import load_extract_index, lookup_extract
from mmi.analysis.reprocess import apply_quality_override, refresh_dashboard
from mmi.analysis.status import collect_analysis_status
from mmi.corpus.paths import DEFAULT_EXTRACT_FULL


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _save_manifest(manifest_path: Path, manifest: dict[str, Any]) -> None:
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _match_entry(entry: dict[str, Any], row: dict[str, Any]) -> bool:
    if row.get("absolute_path") and entry.get("absolute_path") == row.get("absolute_path"):
        return True
    name = (row.get("name") or "").lower()
    rel = (row.get("relative_path") or "").lower()
    return (
        (entry.get("name") or "").lower() == name
        and (entry.get("relative_path") or "").lower() == rel
    )


def exclude_review_entries(
    manifest_path: Path,
    rows: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> list[str]:
    manifest = _load_manifest(manifest_path)
    excluded: list[str] = []
    for row in rows:
        for entry in manifest.get("files") or []:
            if entry.get("include_in_analysis") is False:
                continue
            if not _match_entry(entry, row):
                continue
            excluded.append(f"{entry.get('name')} | {(entry.get('relative_path') or '')[:80]}")
            if not dry_run:
                entry["include_in_analysis"] = False
    if excluded and not dry_run:
        _save_manifest(manifest_path, manifest)
    return excluded


def restore_validacion_bulk_exclusion(manifest_path: Path, *, dry_run: bool = False) -> int:
    """Re-incluye copias VALIDACION excluidas por error (excepto Listado Maestro duplicado)."""
    manifest = _load_manifest(manifest_path)
    restored = 0
    for entry in manifest.get("files") or []:
        rel = (entry.get("relative_path") or "").upper()
        name = entry.get("name") or ""
        if entry.get("include_in_analysis") is not False:
            continue
        if "VALIDACION" not in rel:
            continue
        if name == "Listado Maestro Repuestos PTS DCH Rev A Cponce.xlsx":
            continue
        if not dry_run:
            entry["include_in_analysis"] = True
        restored += 1
    if restored and not dry_run:
        _save_manifest(manifest_path, manifest)
    return restored


def approve_review_items(
    rows: list[dict[str, Any]],
    extract_root: Path,
    *,
    dry_run: bool = False,
) -> list[str]:
    extract_index = load_extract_index()
    approved: list[str] = []
    for row in rows:
        name = row.get("name") or ""
        rel = (row.get("relative_path") or "").upper()
        index_status = row.get("index_status")
        if "PAPELERA" in rel or "VALIDACION" in rel:
            continue
        if name.lower().endswith(".pptx") and "etapa de ejecucion" in name.lower():
            continue
        if index_status != "active" and not (
            name.lower().endswith(".pdf") and "etapa de ejecucion" in name.lower()
        ):
            continue
        entry_path = row.get("absolute_path")
        hit = lookup_extract(entry_path, extract_index) if entry_path else None
        if not hit or not hit.get("extract_dir"):
            continue
        note = "Aprobado pre-RAG: indexado activo" if index_status == "active" else "Aprobado pre-RAG: diagrama PDF"
        approved.append(name)
        if not dry_run:
            apply_quality_override(
                Path(hit["extract_dir"]),
                "pass",
                note=note,
                source="close_pre_rag",
            )
    return approved


def triage_pre_rag(
    *,
    out_dir: Path,
    manifest_path: Path,
    extract_root: Path,
    dry_run: bool = False,
    restore_validacion: bool = True,
) -> dict[str, Any]:
    status_path = out_dir / "analysis-status.json"
    if not status_path.exists():
        return {"error": "sin analysis-status.json"}
    data = json.loads(status_path.read_text(encoding="utf-8"))
    reviews = [a for a in data.get("analyses") or [] if a.get("status") == "review"]

    to_exclude: list[dict[str, Any]] = []
    for row in reviews:
        rel = (row.get("relative_path") or "").upper()
        name = row.get("name") or ""
        if "PAPELERA" in rel:
            to_exclude.append(row)
        elif "VALIDACION" in rel and name == "Listado Maestro Repuestos PTS DCH Rev A Cponce.xlsx":
            to_exclude.append(row)
        elif name == "Etapa de Ejecucion.pptx":
            to_exclude.append(row)

    excluded = exclude_review_entries(manifest_path, to_exclude, dry_run=dry_run)
    restored = 0
    if restore_validacion and not dry_run:
        restored = restore_validacion_bulk_exclusion(manifest_path, dry_run=dry_run)

    approved = approve_review_items(reviews, extract_root, dry_run=dry_run)

    if not dry_run:
        refresh_dashboard(manifest_path, extract_root, out_dir)
        summary = json.loads((out_dir / "analysis-status.json").read_text(encoding="utf-8")).get(
            "summary", {}
        )
    else:
        payload = collect_analysis_status(manifest_path, extract_root, out_dir=out_dir)
        summary = payload.get("summary", {})

    return {
        "dry_run": dry_run,
        "review_total": len(reviews),
        "excluded": len(excluded),
        "restored_validacion": restored,
        "approved_pass": len(approved),
        "details": {
            "excluded": excluded,
            "approved": approved,
        },
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Triaje pre-validación RAG")
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--extract-dir", type=Path, default=DEFAULT_EXTRACT_FULL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-restore-validacion",
        action="store_true",
        help="No re-incluir copias VALIDACION excluidas por error previo",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    out_dir = args.out if args.out.is_absolute() else repo / args.out
    manifest = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    extract_root = args.extract_dir if args.extract_dir.is_absolute() else repo / args.extract_dir

    result = triage_pre_rag(
        out_dir=out_dir,
        manifest_path=manifest,
        extract_root=extract_root,
        dry_run=args.dry_run,
        restore_validacion=not args.no_restore_validacion,
    )
    out_json = out_dir / "close-pre-rag.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    label = "Dry-run" if args.dry_run else "Triaje"
    print(
        f"{label}: {result.get('review_total', 0)} review · "
        f"{result.get('excluded', 0)} excluidos · "
        f"{result.get('restored_validacion', 0)} VALIDACION restaurados · "
        f"{result.get('approved_pass', 0)} pass → {out_json}"
    )
    s = result.get("summary") or {}
    if s:
        print(
            f"Fase 0: {s.get('pass', '?')} pass · {s.get('review', '?')} review · "
            f"excluidos {s.get('excluido', '?')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
