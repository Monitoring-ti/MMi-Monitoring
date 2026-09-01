"""Evaluación golden set C3: recall@k, MRR, precision@k."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from mmi.eval.retrieval import (
    aggregate_metrics,
    case_relevant_spec,
    is_relevant_hit,
    load_golden_cases,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from mmi.motor.analyze import build_search_query, resolve_asset
from mmi.search.engine import HybridSearchEngine


def _build_query(case: dict[str, Any]) -> str:
    if case.get("category") == "motor" and case.get("asset_id") and case.get("symptom"):
        asset = resolve_asset(case["asset_id"])
        return build_search_query(case["symptom"], asset)
    return (case.get("query") or "").strip()


def evaluate_case(
    case: dict[str, Any],
    engine: HybridSearchEngine,
    *,
    k_max: int,
    lexical_rerank: bool = True,
) -> dict[str, Any]:
    query = _build_query(case)
    spec = case_relevant_spec(case)
    row: dict[str, Any] = {
        "id": case.get("id") or query[:40],
        "category": case.get("category") or "",
        "query": query,
        "original_query": case.get("query") or "",
    }
    if case.get("asset_id"):
        row["asset_id"] = case["asset_id"]

    hits = engine.search(query, limit=k_max, lexical_rerank=lexical_rerank)
    row["hit_count"] = len(hits)
    row["mrr"] = reciprocal_rank(hits, spec)
    for k in (1, 3, 5, 8):
        if k <= k_max:
            row[f"recall@{k}"] = recall_at_k(hits, spec, k)
            row[f"precision@{k}"] = precision_at_k(hits, spec, k)

    row["top_hits"] = [
        {
            "rank": i,
            "score": round(float(h.score), 4),
            "titulo": h.titulo,
            "tipo": h.tipo,
            "relevant": is_relevant_hit(h, spec) if spec else False,
        }
        for i, h in enumerate(hits[:5], 1)
    ]
    row["ok"] = row.get("recall@5", 0.0) >= 1.0
    return row


def run_eval(
    cases: list[dict[str, Any]],
    *,
    tenant: str = "monitoring",
    k_max: int = 8,
    lexical_rerank: bool = True,
) -> dict[str, Any]:
    engine = HybridSearchEngine(tenant_slug=tenant)
    rows = [
        evaluate_case(case, engine, k_max=k_max, lexical_rerank=lexical_rerank) for case in cases
    ]
    metrics = aggregate_metrics(rows, k_values=[1, 3, 5, 8])
    passed = sum(1 for r in rows if r.get("ok"))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tenant": tenant,
        "k_max": k_max,
        "lexical_rerank": lexical_rerank,
        "case_count": len(cases),
        "summary": {
            **metrics,
            "passed_recall@5": passed,
            "pass_rate_recall@5": round(passed / len(cases), 4) if cases else 0.0,
        },
        "cases": rows,
    }


def render_html(report: dict[str, Any]) -> str:
    s = report.get("summary") or {}
    rows_html: list[str] = []
    for case in report.get("cases") or []:
        status = "ok" if case.get("ok") else "fail"
        tops = "<br>".join(
            f"#{h['rank']} {'✓' if h.get('relevant') else '·'} {escape(str(h.get('titulo') or '')[:70])} ({h.get('score')})"
            for h in (case.get("top_hits") or [])
        )
        rows_html.append(
            f"""<tr class="{status}">
  <td>{escape(str(case.get('id')))}</td>
  <td>{escape(str(case.get('category')))}</td>
  <td>{escape(str(case.get('query')))[:120]}</td>
  <td>{case.get('mrr', 0):.3f}</td>
  <td>{'✓' if case.get('recall@5') else '✗'}</td>
  <td>{case.get('recall@1', 0):.0%} / {case.get('recall@3', 0):.0%} / {case.get('recall@5', 0):.0%}</td>
  <td><small>{tops}</small></td>
</tr>"""
        )

    by_cat = s.get("by_category") or {}
    cat_rows = "".join(
        f"<tr><td>{escape(cat)}</td><td>{b.get('count')}</td>"
        f"<td>{b.get('mrr', 0):.3f}</td><td>{b.get('recall@5', 0):.0%}</td></tr>"
        for cat, b in sorted(by_cat.items())
    )

    return f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><title>Golden set C3 — evaluación recuperación</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #0f1419; color: #e6edf3; }}
h1 {{ font-size: 1.4rem; }}
.meta {{ color: #8b949e; margin-bottom: 20px; }}
.stats {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; min-width: 120px; }}
.card b {{ display: block; font-size: 1.5rem; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 24px; }}
th, td {{ border: 1px solid #30363d; padding: 8px; vertical-align: top; }}
th {{ background: #161b22; text-align: left; }}
tr.ok td {{ background: rgba(46,160,67,.08); }}
tr.fail td {{ background: rgba(248,81,73,.08); }}
small {{ color: #8b949e; }}
a {{ color: #58a6ff; }}
</style></head><body>
<h1>Golden set C3 — evaluación recuperación</h1>
<p class="meta">Generado {escape(str(report.get('generated_at')))} · tenant {escape(str(report.get('tenant')))} · {report.get('case_count')} casos</p>
<div class="stats">
  <div class="card"><b>{s.get('passed_recall@5', 0)}/{s.get('total', 0)}</b> recall@5 OK</div>
  <div class="card"><b>{s.get('mrr', 0):.3f}</b> MRR</div>
  <div class="card"><b>{s.get('recall@1', 0):.0%}</b> recall@1</div>
  <div class="card"><b>{s.get('recall@3', 0):.0%}</b> recall@3</div>
  <div class="card"><b>{s.get('recall@5', 0):.0%}</b> recall@5</div>
  <div class="card"><b>{s.get('pass_rate_recall@5', 0):.0%}</b> pass rate</div>
</div>
<p><a href="search.html">Búsqueda</a> · <a href="rag.html">RAG</a> · <a href="motor.html">Motor MMI</a> · <a href="rag-validation.html">Validación RAG</a></p>
<h2>Por categoría</h2>
<table><thead><tr><th>Categoría</th><th>N</th><th>MRR</th><th>recall@5</th></tr></thead><tbody>{cat_rows}</tbody></table>
<h2>Casos</h2>
<table>
<thead><tr><th>ID</th><th>Cat.</th><th>Consulta</th><th>MRR</th><th>R@5</th><th>R@1/3/5</th><th>Top hits</th></tr></thead>
<tbody>{"".join(rows_html)}</tbody>
</table>
</body></html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluación golden set C3 (recall@k, MRR)")
    parser.add_argument("--cases", type=Path, default=Path("fixtures/golden-set-retrieval.json"))
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--k", type=int, default=8, help="Top-k máximo para evaluación")
    parser.add_argument("--no-rerank", action="store_true", help="Desactivar reranker léxico C1")
    parser.add_argument(
        "--compare-rerank",
        action="store_true",
        help="Comparar baseline (sin rerank) vs reranker C1",
    )
    parser.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    cases_path = args.cases if args.cases.is_absolute() else repo / args.cases
    out_dir = args.out if args.out.is_absolute() else repo / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = load_golden_cases(cases_path)

    if args.compare_rerank:
        print(f"Comparativa C1 · {len(cases)} casos · k_max={args.k}")
        baseline = run_eval(cases, tenant=args.tenant, k_max=args.k, lexical_rerank=False)
        reranked = run_eval(cases, tenant=args.tenant, k_max=args.k, lexical_rerank=True)
        bs, rs = baseline["summary"], reranked["summary"]
        delta = {
            "mrr": round((rs.get("mrr") or 0) - (bs.get("mrr") or 0), 4),
            "recall@5": round((rs.get("recall@5") or 0) - (bs.get("recall@5") or 0), 4),
            "pass_delta": (rs.get("passed_recall@5") or 0) - (bs.get("passed_recall@5") or 0),
        }
        report = {
            "mode": "compare",
            "baseline": baseline,
            "reranked": reranked,
            "delta": delta,
        }
        json_path = out_dir / "golden-set-rerank-compare.json"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"baseline MRR={bs.get('mrr')} R@5={bs.get('recall@5')} · "
            f"rerank MRR={rs.get('mrr')} R@5={rs.get('recall@5')} · "
            f"Δ MRR={delta['mrr']:+.4f} Δ R@5={delta['recall@5']:+.4f}"
        )
        print(f"JSON → {json_path.resolve()}")
        return 0

    use_rerank = not args.no_rerank
    print(f"Golden set C3 · {len(cases)} casos · k_max={args.k} · rerank={use_rerank}")
    report = run_eval(cases, tenant=args.tenant, k_max=args.k, lexical_rerank=use_rerank)

    json_path = out_dir / "golden-set-eval.json"
    html_path = out_dir / "golden-set-eval.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")

    s = report["summary"]
    print(
        f"MRR={s.get('mrr')} · recall@5={s.get('recall@5')} · "
        f"pass {s.get('passed_recall@5')}/{s.get('total')} ({s.get('pass_rate_recall@5'):.0%})"
    )
    print(f"JSON → {json_path.resolve()}")
    print(f"HTML → {html_path.resolve()}")
    return 0 if s.get("passed_recall@5") == s.get("total") else 1


if __name__ == "__main__":
    raise SystemExit(main())
