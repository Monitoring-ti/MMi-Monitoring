"""Indexación masiva del corpus (manifest + extracciones Fase 0)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from mmi.analysis.live_status import append_ingestion_log
from mmi.analysis.status import collect_analysis_status, write_review_pages
from mmi.analysis.review_shell import write_review_dashboard
from mmi.corpus.paths import DEFAULT_EXTRACT_FULL
from mmi.index.manifest_index import indexable_from_manifest
from mmi.index.pipeline import ingest_file


def _save_summary(path: Path, results: list[dict], *, meta: dict) -> None:
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **meta,
        "results": results,
        "stats": _stats(results),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _stats(results: list[dict]) -> dict:
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


def _terminal_estados(*, retry_errors: bool = False) -> frozenset[str]:
    base = {"active", "indexed", "indexado", "duplicado", "mismo_contenido", "needs_review"}
    if not retry_errors:
        base = base | {"error"}
    return frozenset(base)


def _load_resume_map(summary_path: Path) -> dict[str, dict]:
    if not summary_path.exists():
        return {}
    try:
        raw = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = raw.get("results") or []
    return {r["archivo"]: r for r in rows if r.get("archivo")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Indexar corpus ODS1 en Supabase + Qdrant")
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--extract-dir", type=Path, default=DEFAULT_EXTRACT_FULL)
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--out", type=Path, default=Path("out/index-corpus-summary.json"))
    parser.add_argument("--limit", type=int, help="Máximo de documentos a indexar")
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Indexar sin activar versión (status indexed)",
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Omitir archivos ya registrados en index-corpus-summary.json (default: true)",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Con --resume, reintentar solo filas con estado error",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    manifest_path = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    extract_root = args.extract_dir if args.extract_dir.is_absolute() else repo / args.extract_dir

    out_path = args.out if args.out.is_absolute() else repo / args.out
    prior = _load_resume_map(out_path) if args.resume else {}
    terminal = _terminal_estados(retry_errors=args.retry_errors)

    files = indexable_from_manifest(manifest_path, extract_root)

    if not files:
        print("No hay archivos indexables (quality pass + manifest).")
        print(f"Manifest: {manifest_path}")
        print(f"Extract:  {extract_root}")
        return 1

    results: list[dict] = []
    if prior and args.resume:
        before = len(files)
        if args.retry_errors:
            error_names = {
                name for name, row in prior.items() if row.get("estado") == "error"
            }
            files = [item for item in files if item["name"] in error_names]
            results = [r for r in prior.values() if r.get("estado") != "error"]
            if error_names:
                print(f"Retry: reintentando {len(files)} con error previo")
        else:
            files = [
                item
                for item in files
                if prior.get(item["name"], {}).get("estado") not in terminal
            ]
            results = list(prior.values())
            skipped = before - len(files)
            if skipped:
                print(f"Resume: omitidos {skipped} ya procesados ({out_path.name})")

    if args.limit:
        files = files[: args.limit]

    if not files:
        print("Nada pendiente de indexar.")
        stats = (json.loads(out_path.read_text(encoding="utf-8")).get("stats") if out_path.exists() else {}) or {}
        print(f"Resumen previo → {out_path.resolve()}")
        print(json.dumps(stats, ensure_ascii=False))
        return 0

    print(f"Indexando {len(files)} documentos desde {extract_root.name}…")
    start_count = len(results)
    total_target = start_count + len(files)
    for i, item in enumerate(files, 1):
        try:
            res = ingest_file(
                item["path"],
                tenant_slug=args.tenant,
                tipo=item["tipo"],
                version_label=item.get("version_label") or None,
                document_key=item["document_key"],
                relative_path=item.get("relative_path") or "",
                origen=item.get("origen") or "ods1",
                activate=not args.no_activate,
            )
        except Exception as exc:  # noqa: BLE001
            res = {"archivo": item["name"], "estado": "error", "detalle": str(exc)[:300]}
        results.append(res)
        mark = res.get("estado", "?")
        chunks = res.get("chunks", 0)
        seq = start_count + i
        line = f"[{seq}/{total_target}] {mark:14} {chunks:4} ch  {item['name'][:70]}"
        print(line)
        append_ingestion_log(manifest_path.parent, "index-corpus.log", line)
        _save_summary(
            out_path,
            results,
            meta={
                "manifest": str(manifest_path),
                "extract_dir": str(extract_root),
                "tenant": args.tenant,
                "progress": f"{seq}/{total_target}",
            },
        )

    stats = _stats(results)
    print(f"\nResumen → {out_path.resolve()}")
    print(
        f"Indexados: {stats['indexados']} ({stats['chunks']} chunks, {stats['tokens']} tokens) · "
        f"Duplicados: {stats['duplicados']} · Mismo contenido: {stats['mismo_contenido']} · "
        f"Needs review: {stats['needs_review']} · Errores: {stats['errores']}"
    )

    if extract_root.exists():
        write_review_pages(extract_root)
        out_dir = manifest_path.parent
        status_payload = collect_analysis_status(manifest_path, extract_root, out_dir=manifest_path.parent)
        write_review_dashboard(out_dir, status_payload)

    return 0 if stats["errores"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
