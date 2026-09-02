"""CLI — pagina de resultados de ingesta."""

from __future__ import annotations

import argparse
from pathlib import Path

from mmi.analysis.ingestion_results import build_ingestion_results, write_ingestion_results
from mmi.tools.console import configure_stdout_utf8


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera ingestion-results.html + JSON")
    parser.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)

    configure_stdout_utf8()
    out_dir = args.out if args.out.is_absolute() else Path.cwd() / args.out
    json_path, html_path = write_ingestion_results(out_dir)
    report = build_ingestion_results(out_dir)
    cs = report.get("summary") or {}
    print(f"Ingesta · pass {cs.get('pass', '?')} · index {cs.get('indexados', '?')} · {report.get('document_count', '?')} docs")
    print(f"JSON -> {json_path.resolve()}")
    print(f"HTML -> {html_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
