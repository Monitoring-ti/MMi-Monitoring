"""CLI: sincronizar index-corpus-summary.json desde Postgres."""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from mmi.analysis.review_shell import write_review_dashboard
from mmi.analysis.status import collect_analysis_status
from mmi.corpus.paths import DEFAULT_EXTRACT_FULL
from mmi.index.summary_sync import sync_index_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sincroniza index-corpus-summary.json con Postgres")
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--out", type=Path, default=Path("out/index-corpus-summary.json"))
    parser.add_argument("--extract-dir", type=Path, default=DEFAULT_EXTRACT_FULL)
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--refresh-dashboard", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    manifest = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    out_path = args.out if args.out.is_absolute() else repo / args.out
    extract_root = args.extract_dir if args.extract_dir.is_absolute() else repo / args.extract_dir

    report = sync_index_summary(manifest, out_path, tenant_slug=args.tenant)
    stats = report["stats"]
    print(f"Sincronizado → {out_path.resolve()}")
    print(
        f"Indexados: {stats['indexados']} ({stats['chunks']} chunks) · "
        f"Duplicados: {stats['duplicados']} · Errores: {stats['errores']} · "
        f"Filas actualizadas: {report['updated_rows']}"
    )

    if args.refresh_dashboard:
        payload = collect_analysis_status(manifest, extract_root, out_dir=manifest.parent)
        write_review_dashboard(manifest.parent, payload)
        print(f"Dashboard → {(manifest.parent / 'review.html').resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
