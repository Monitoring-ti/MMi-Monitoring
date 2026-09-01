"""Genera dashboard de estado por análisis y páginas de revisión."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mmi.analysis.status import (
    collect_analysis_status,
    write_review_pages,
)
from mmi.analysis.review_shell import write_review_dashboard
from mmi.corpus.paths import DEFAULT_EXTRACT_FULL


def build_status(
    manifest_path: Path,
    extract_root: Path,
    out_dir: Path,
    *,
    skip_reviews: bool = False,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    n_reviews = 0 if skip_reviews else write_review_pages(extract_root)
    payload = collect_analysis_status(
        manifest_path,
        extract_root,
        out_dir=out_dir,
    )

    hub = write_review_dashboard(out_dir, payload)

    from mmi.corpus.remote_source import load_remote_source
    from mmi.tools.source_review import render_source_review_page

    remote = load_remote_source(out_dir / "remote-source.json")
    (out_dir / "source-review.html").write_text(
        render_source_review_page(remote), encoding="utf-8"
    )

    print(f"Estado JSON → {(out_dir / 'analysis-status.json').resolve()}")
    print(f"Dashboard   → {hub.resolve()}")
    print(f"Vistas revisión: {n_reviews}")
    s = payload.get("summary") or {}
    print(
        f"Resumen: {s.get('pass', 0)} OK · {s.get('reject', 0)} rechazados · "
        f"{s.get('pendiente_extractor', 0)} pend. PDF/OCR"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dashboard estado Fase 0 por análisis")
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--extract-dir", type=Path, default=DEFAULT_EXTRACT_FULL)
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--serve", action="store_true", help="Servir carpeta out/ en http://127.0.0.1:PORT")
    parser.add_argument("--port", type=int, default=8772)
    parser.add_argument("--skip-reviews", action="store_true", help="No regenerar review.html por documento")
    args = parser.parse_args(argv)

    repo = Path.cwd()
    manifest = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    extract_root = args.extract_dir if args.extract_dir.is_absolute() else repo / args.extract_dir
    out_dir = args.out if args.out.is_absolute() else repo / args.out

    build_status(manifest, extract_root, out_dir, skip_reviews=args.skip_reviews)

    if args.serve:
        from mmi.tools.out_handler import make_out_handler

        handler = make_out_handler(out_dir)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        print(f"\nAbre http://127.0.0.1:{args.port}/review.html")
        print("APIs ingesta: /api/ingestion-action · /api/ingestion-live")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nDetenido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
