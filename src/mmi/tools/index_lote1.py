"""Indexa el lote 1 (Rev 6 vigente) en Supabase + Qdrant."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from mmi.analysis.status import collect_analysis_status, write_review_pages
from mmi.analysis.review_shell import write_review_dashboard
from mmi.corpus.paths import DEFAULT_EXTRACT_LOTE1
from mmi.index.manifest_index import indexable_from_manifest
from mmi.index.pipeline import ingest_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Indexar lote 1 en Supabase + Qdrant")
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--extract-dir", type=Path, default=DEFAULT_EXTRACT_LOTE1)
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--out", type=Path, default=Path("out/index-lote1-summary.json"))
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    manifest_path = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    extract_root = args.extract_dir if args.extract_dir.is_absolute() else repo / args.extract_dir

    files = indexable_from_manifest(manifest_path, extract_root)
    if not files:
        print("No hay archivos indexables (quality pass).")
        return 1

    print(f"Indexando {len(files)} documentos…")
    results: list[dict] = []
    for item in files:
        try:
            res = ingest_file(
                item["path"],
                tenant_slug=args.tenant,
                tipo=item["tipo"],
                version_label=item.get("version_label"),
                document_key=item.get("document_key") or item.get("name"),
            )
        except Exception as exc:  # noqa: BLE001
            res = {"archivo": item["name"], "estado": "error", "detalle": str(exc)[:300]}
        results.append(res)
        print(res)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResumen → {args.out.resolve()}")

    ok = [r for r in results if r.get("estado") in {"active", "indexed", "indexado"}]
    dup = [r for r in results if r.get("estado") == "duplicado"]
    err = [r for r in results if r.get("estado") == "error"]
    print(
        f"Indexados: {len(ok)} ({sum(r.get('chunks', 0) for r in ok)} chunks) · "
        f"Duplicados: {len(dup)} · Errores: {len(err)}"
    )

    write_review_pages(extract_root)
    status_payload = collect_analysis_status(
        manifest_path, extract_root, out_dir=manifest_path.parent
    )
    out_dir = manifest_path.parent
    write_review_dashboard(out_dir, status_payload)

    return 0 if not err else 1


if __name__ == "__main__":
    raise SystemExit(main())
