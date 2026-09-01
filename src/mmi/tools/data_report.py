"""CLI Fase D — informe unificado de análisis de datos."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mmi.analysis.data_report import build_data_report, render_data_report_html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Informe análisis de datos (Fase D)")
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--analysis-dir", type=Path, default=None, help="Salida data-analysis/")
    args = parser.parse_args(argv)

    repo = Path.cwd()
    out_dir = args.out if args.out.is_absolute() else repo / args.out
    analysis_dir = args.analysis_dir or (out_dir / "data-analysis")
    analysis_dir.mkdir(parents=True, exist_ok=True)

    report = build_data_report(out_dir)
    json_path = analysis_dir / "report.json"
    html_path = out_dir / "data-quality.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_data_report_html(report), encoding="utf-8")

    cs = report.get("corpus_summary") or {}
    print(f"Fase D · pass {cs.get('pass', '?')} · index {cs.get('indexados', '?')}")
    print(f"JSON  → {json_path.resolve()}")
    print(f"HTML  → {html_path.resolve()}")
    for line in report.get("recommendations") or []:
        print(f"  · {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
