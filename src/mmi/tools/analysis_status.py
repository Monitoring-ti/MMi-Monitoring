"""Genera dashboard de estado por análisis y páginas de revisión."""

from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mmi.analysis.status import (
    collect_analysis_status,
    render_dashboard,
    write_review_pages,
)


def build_status(
    manifest_path: Path,
    extract_root: Path,
    out_dir: Path,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    n_reviews = write_review_pages(extract_root)
    payload = collect_analysis_status(manifest_path, extract_root)

    json_path = out_dir / "analysis-status.json"
    html_path = out_dir / "analysis-status.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_dashboard(payload), encoding="utf-8")

    from mmi.corpus.remote_source import load_remote_source
    from mmi.tools.source_review import render_source_review_page

    remote = load_remote_source(out_dir / "remote-source.json")
    (out_dir / "source-review.html").write_text(
        render_source_review_page(remote), encoding="utf-8"
    )

    print(f"Estado JSON → {json_path.resolve()}")
    print(f"Dashboard   → {html_path.resolve()}")
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
    parser.add_argument("--extract-dir", type=Path, default=Path("out/lote1-extract"))
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--serve", action="store_true", help="Servir carpeta out/ en http://127.0.0.1:PORT")
    parser.add_argument("--port", type=int, default=8772)
    args = parser.parse_args(argv)

    repo = Path.cwd()
    manifest = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    extract_root = args.extract_dir if args.extract_dir.is_absolute() else repo / args.extract_dir
    out_dir = args.out if args.out.is_absolute() else repo / args.out

    build_status(manifest, extract_root, out_dir)

    if args.serve:
        handler = lambda *h, **k: SimpleHTTPRequestHandler(  # noqa: E731
            *h, directory=str(out_dir.resolve()), **k
        )
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        print(f"\nAbre http://127.0.0.1:{args.port}/analysis-status.html")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nDetenido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
