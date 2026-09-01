"""Validación RAG: búsqueda + respuesta con citas sobre corpus ODS1 indexado."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from mmi.search.answer import ask as rag_ask, extract_cited_indices
from mmi.search.engine import HybridSearchEngine


def _load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        return data["cases"]
    raise ValueError("JSON debe ser lista de casos o {\"cases\": [...]}")


def _keyword_hit(text: str, keywords: list[str]) -> bool:
    upper = text.upper()
    return any(k.upper() in upper for k in keywords)


def _evaluate_search(hits: list[Any], expect_keywords: list[str]) -> dict[str, Any]:
    if not hits:
        return {"ok": False, "reason": "sin resultados", "top_score": 0.0}
    top = hits[0]
    top_text = f"{top.titulo or ''} {top.content or ''} {top.citation or ''}"
    kw_ok = True
    if expect_keywords:
        pool = " ".join(
            f"{h.titulo or ''} {h.content or ''}" for h in hits[:3]
        )
        kw_ok = _keyword_hit(pool, expect_keywords)
    return {
        "ok": True,
        "keyword_match": kw_ok,
        "top_score": round(float(top.score), 4),
        "top_titulo": top.titulo,
        "count": len(hits),
    }


def _evaluate_answer(result: Any) -> dict[str, Any]:
    answer = result.answer or ""
    cited = extract_cited_indices(answer)
    has_resumen = "## resumen" in answer.lower() or "## Resumen" in answer
    has_detail = "## detalle" in answer.lower() or "## Detalle" in answer
    no_evidence = "no encontr" in answer.lower() and not cited
    ok = bool(cited) and has_resumen and not no_evidence
    return {
        "ok": ok,
        "citations": len(cited),
        "references": len(result.references),
        "has_resumen": has_resumen,
        "has_detalle": has_detail,
        "model": result.model,
        "answer_preview": answer[:400].strip(),
    }


def run_validation(
    cases: list[dict[str, Any]],
    *,
    tenant: str = "monitoring",
    limit: int = 6,
    skip_ask: bool = False,
) -> dict[str, Any]:
    engine = HybridSearchEngine(tenant_slug=tenant)
    rows: list[dict[str, Any]] = []
    search_ok = ask_ok = 0

    for case in cases:
        query = (case.get("query") or "").strip()
        expect = [str(k) for k in (case.get("expect_keywords") or [])]
        row: dict[str, Any] = {
            "id": case.get("id") or query[:40],
            "category": case.get("category") or "",
            "query": query,
        }
        try:
            hits = engine.search(query, limit=limit)
            search_eval = _evaluate_search(hits, expect)
            row["search"] = search_eval
            if search_eval.get("ok"):
                search_ok += 1
            if search_eval.get("keyword_match") is False:
                row["search"]["warn"] = f"keywords no en top-3: {expect}"

            if skip_ask:
                row["ask"] = {"skipped": True}
            else:
                result = rag_ask(query, engine, limit=limit)
                ask_eval = _evaluate_answer(result)
                row["ask"] = ask_eval
                row["ask"]["top_refs"] = [
                    {
                        "index": r.get("index"),
                        "titulo": r.get("titulo"),
                        "citation": r.get("citation"),
                    }
                    for r in (result.references or [])[:3]
                ]
                if ask_eval.get("ok"):
                    ask_ok += 1
        except Exception as exc:  # noqa: BLE001
            row["error"] = str(exc)[:300]

        rows.append(row)

    total = len(cases)
    passed = sum(
        1
        for r in rows
        if r.get("search", {}).get("ok")
        and (skip_ask or r.get("ask", {}).get("ok"))
        and not r.get("error")
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tenant": tenant,
        "limit": limit,
        "skip_ask": skip_ask,
        "summary": {
            "total": total,
            "passed": passed,
            "search_ok": search_ok,
            "ask_ok": ask_ok if not skip_ask else None,
            "pass_rate": round(passed / total, 3) if total else 0.0,
        },
        "cases": rows,
    }


def render_html(report: dict[str, Any]) -> str:
    s = report.get("summary") or {}
    rows_html: list[str] = []
    for case in report.get("cases") or []:
        se = case.get("search") or {}
        ae = case.get("ask") or {}
        status = "ok" if (
            se.get("ok")
            and (report.get("skip_ask") or ae.get("ok"))
            and not case.get("error")
        ) else "fail"
        badge = "ok" if status == "ok" else "bad"
        refs = ""
        if ae.get("top_refs"):
            refs = "<ul>" + "".join(
                f"<li>[{escape(str(r.get('index')))}] {escape(str(r.get('titulo') or r.get('citation') or ''))}</li>"
                for r in ae["top_refs"]
            ) + "</ul>"
        rows_html.append(
            f"""<tr class="{badge}">
  <td>{escape(str(case.get('id')))}</td>
  <td>{escape(str(case.get('category')))}</td>
  <td>{escape(str(case.get('query')))}</td>
  <td>{'✓' if se.get('ok') else '✗'} · score {se.get('top_score', '—')}<br><small>{escape(str(se.get('top_titulo') or ''))[:80]}</small></td>
  <td>{'—' if report.get('skip_ask') else ('✓' if ae.get('ok') else '✗')} · {ae.get('citations', '—')} citas</td>
  <td>{refs}</td>
  <td>{escape(str(case.get('error') or se.get('warn') or ''))}</td>
</tr>"""
        )

    return f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><title>Validación RAG ODS1</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #0f1419; color: #e6edf3; }}
h1 {{ font-size: 1.4rem; }}
.meta {{ color: #8b949e; margin-bottom: 20px; }}
.stats {{ display: flex; gap: 16px; margin-bottom: 24px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; }}
.card b {{ display: block; font-size: 1.5rem; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
th, td {{ border: 1px solid #30363d; padding: 8px; vertical-align: top; }}
th {{ background: #161b22; text-align: left; }}
tr.ok td {{ background: rgba(46,160,67,.08); }}
tr.fail td {{ background: rgba(248,81,73,.08); }}
small {{ color: #8b949e; }}
a {{ color: #58a6ff; }}
</style></head><body>
<h1>Validación RAG — corpus ODS1</h1>
<p class="meta">Generado {escape(str(report.get('generated_at')))} · tenant {escape(str(report.get('tenant')))}</p>
<div class="stats">
  <div class="card"><b>{s.get('passed', 0)}/{s.get('total', 0)}</b> casos OK</div>
  <div class="card"><b>{s.get('search_ok', 0)}</b> búsqueda</div>
  <div class="card"><b>{s.get('ask_ok', '—')}</b> RAG con citas</div>
  <div class="card"><b>{int((s.get('pass_rate') or 0) * 100)}%</b> pass rate</div>
</div>
<p><a href="rag.html">Consulta RAG</a> · <a href="search.html">Búsqueda</a> · <a href="review.html">Revisión</a></p>
<table>
<thead><tr><th>ID</th><th>Categoría</th><th>Consulta</th><th>Búsqueda</th><th>RAG</th><th>Referencias</th><th>Notas</th></tr></thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table>
</body></html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validación RAG sobre corpus indexado")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("fixtures/rag-validation-queries.json"),
    )
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--search-only", action="store_true", help="Solo búsqueda, sin OpenRouter")
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    cases_path = args.cases if args.cases.is_absolute() else repo / args.cases
    out_dir = args.out if args.out.is_absolute() else repo / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = _load_cases(cases_path)
    print(f"Validación RAG · {len(cases)} casos · limit={args.limit}")
    report = run_validation(
        cases,
        tenant=args.tenant,
        limit=args.limit,
        skip_ask=args.search_only,
    )

    json_path = out_dir / "rag-validation.json"
    html_path = out_dir / "rag-validation.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")

    s = report["summary"]
    print(
        f"Resultado: {s['passed']}/{s['total']} OK · "
        f"búsqueda {s['search_ok']}/{s['total']}"
        + (f" · RAG {s['ask_ok']}/{s['total']}" if s.get("ask_ok") is not None else "")
    )
    print(f"JSON  → {json_path.resolve()}")
    print(f"HTML  → {html_path.resolve()}")
    return 0 if s["passed"] == s["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
