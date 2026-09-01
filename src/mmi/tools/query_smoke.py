"""Smoke test mínimo: búsqueda indexada + URLs para probar consultas (sin OpenRouter)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

from mmi.search.rag_page import render_rag_html
from mmi.tools.search_cli import render_search_html
from mmi.tools.validate_rag import _load_cases, run_validation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test de consultas (solo búsqueda)")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("fixtures/consultas-prueba.json"),
    )
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--port", type=int, default=8773)
    parser.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    cases_path = args.cases if args.cases.is_absolute() else repo / args.cases
    out_dir = args.out if args.out.is_absolute() else repo / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = _load_cases(cases_path)
    report = run_validation(cases, tenant=args.tenant, limit=5, skip_ask=True)

    (out_dir / "search.html").write_text(render_search_html(out_dir), encoding="utf-8")
    (out_dir / "rag.html").write_text(render_rag_html(out_dir), encoding="utf-8")

    smoke_path = out_dir / "query-smoke.json"
    smoke_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    s = report["summary"]
    base = f"http://127.0.0.1:{args.port}"
    print(f"Smoke: {s['passed']}/{s['total']} OK (búsqueda {s['search_ok']}/{s['total']})")
    print(f"Reporte → {smoke_path.resolve()}")
    print()
    print("1. Levantar servidor:")
    print(f"   .venv\\Scripts\\python -m mmi.tools.serve_local --port {args.port}")
    print()
    print("2. Probar en navegador:")
    print(f"   {base}/search.html          — búsqueda híbrida")
    print(f"   {base}/rag.html             — consulta con citas (requiere OpenRouter)")
    for case in cases:
        q = quote(case["query"])
        print(f"   {base}/rag.html?q={q}")
    print()
    print("3. Validación completa (10 casos, opcional RAG):")
    print("   .venv\\Scripts\\python -m mmi.tools.validate_rag --search-only")

    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
