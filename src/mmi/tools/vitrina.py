"""CLI — genera paginas vitrina (pruebas + ejemplos)."""

from __future__ import annotations

import argparse
from pathlib import Path

from mmi.tools.console import configure_stdout_utf8
from mmi.web.vitrina import build_pruebas_report, write_vitrina_pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera index/pruebas/ejemplos.html (modo vitrina)")
    parser.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)

    configure_stdout_utf8()
    out_dir = args.out if args.out.is_absolute() else Path.cwd() / args.out
    paths = write_vitrina_pages(out_dir)
    report = build_pruebas_report(out_dir)
    smoke = (report.get("smoke") or {}).get("summary") or {}
    print(f"Vitrina · smoke {smoke.get('passed', '?')}/{smoke.get('total', '?')}")
    for key, path in paths.items():
        print(f"  {key} -> {path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
