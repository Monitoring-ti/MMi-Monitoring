"""Indexa el lote 1 (Rev 6 vigente) en Supabase + Qdrant."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from mmi.analysis.status import collect_analysis_status, render_dashboard, write_review_pages
from mmi.index.pipeline import ingest_file


def _indexable_from_manifest(manifest_path: Path, extract_root: Path) -> list[dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    indexable: list[dict] = []
    for entry in manifest.get("files") or []:
        abs_path = entry.get("absolute_path")
        if not abs_path or not Path(abs_path).exists():
            continue
        phase0 = entry.get("phase0", "")
        if phase0 not in {"excel", "pdf", "ocr", "pptx"}:
            continue
        from mmi.analysis.status import _find_extract_dir

        extract_dir = _find_extract_dir(extract_root, abs_path)
        if extract_dir and (extract_dir / "extracted.json").exists():
            data = json.loads((extract_dir / "extracted.json").read_text(encoding="utf-8"))
            if data.get("quality") != "pass":
                continue
        elif phase0 in {"excel", "ocr", "pptx"}:
            continue
        tipo = entry.get("suggested_tipo", "otro")
        indexable.append(
            {
                "path": abs_path,
                "name": entry.get("name"),
                "tipo": tipo,
                "document_key": entry.get("document_key"),
                "version_label": entry.get("revision"),
                "is_current": entry.get("is_current", True),
            }
        )
    return indexable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Indexar lote 1 en Supabase + Qdrant")
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--extract-dir", type=Path, default=Path("out/lote1-extract"))
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--out", type=Path, default=Path("out/index-lote1-summary.json"))
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    manifest_path = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    extract_root = args.extract_dir if args.extract_dir.is_absolute() else repo / args.extract_dir

    files = _indexable_from_manifest(manifest_path, extract_root)
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

    ok = [r for r in results if r.get("estado") == "indexado"]
    dup = [r for r in results if r.get("estado") == "duplicado"]
    err = [r for r in results if r.get("estado") == "error"]
    print(
        f"Indexados: {len(ok)} ({sum(r.get('chunks', 0) for r in ok)} chunks) · "
        f"Duplicados: {len(dup)} · Errores: {len(err)}"
    )

    write_review_pages(extract_root)
    status_payload = collect_analysis_status(manifest_path, extract_root)
    out_dir = manifest_path.parent
    (out_dir / "analysis-status.json").write_text(
        json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "analysis-status.html").write_text(
        render_dashboard(status_payload), encoding="utf-8"
    )

    return 0 if not err else 1


if __name__ == "__main__":
    raise SystemExit(main())
