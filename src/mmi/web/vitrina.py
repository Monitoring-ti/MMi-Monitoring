"""Vitrina publica — pruebas + ejemplos (sin ingesta)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from mmi.analysis.data_report import _load_json
from mmi.search.examples import _CATEGORIES, _TIPS, load_corpus_stats
from mmi.web.vitrina_shell import metric_card, render_shell

VITRINA_ROBOTS = "User-agent: *\nDisallow: /\n"


def _href(page: str, query: str | None = None) -> str:
    path = f"/{page.lstrip('/')}"
    if query:
        return f"{path}?q={quote(query, safe='')}"
    return path


def build_pruebas_report(out_dir: Path) -> dict[str, Any]:
    out_dir = Path(out_dir)
    smoke = _load_json(out_dir / "query-smoke.json") or {}
    golden = _load_json(out_dir / "golden-set-eval.json") or {}
    rag_val = _load_json(out_dir / "rag-validation.json") or {}
    load_test = _load_json(out_dir / "load-test-report.json") or {}
    ingestion = _load_json(out_dir / "ingestion-results.json") or {}
    stats = load_corpus_stats(out_dir)

    load_search_p95 = None
    for sc in load_test.get("scenarios") or []:
        if sc.get("name") == "search-direct":
            load_search_p95 = (sc.get("stats") or {}).get("p95_ms")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus": stats,
        "ingestion_summary": (ingestion.get("summary") or {}) if ingestion else {},
        "smoke": smoke,
        "golden": golden,
        "rag_validation": rag_val,
        "load_test_p95_ms": load_search_p95,
    }


def _fmt_pass(summary: dict[str, Any] | None) -> tuple[str, str, bool]:
    if not summary:
        return "—", "fail", False
    passed = summary.get("passed")
    total = summary.get("total")
    if passed is None or total is None:
        return "—", "fail", False
    ok = int(passed) == int(total) and int(total) > 0
    return f"{passed}/{total}", "pass" if ok else "fail", ok


def _status_row(name: str, category: str, query: str, ok: bool, score: str, *, link: str) -> str:
    dot = "bg-green-500" if ok else "bg-error"
    status = "Prueba OK" if ok else "Falló"
    status_cls = "text-on-surface" if ok else "text-error font-semibold"
    return f"""
<tr class="hover:bg-surface-container-low transition-colors">
  <td class="px-margin-mobile py-stack-md">
    <a href="{escape(link)}" class="flex items-center gap-stack-sm group">
      <span class="material-symbols-outlined text-outline group-hover:text-primary">description</span>
      <span class="text-body-md text-primary font-semibold">{escape(name)}</span>
    </a>
  </td>
  <td class="px-margin-mobile py-stack-md">
    <span class="bg-tertiary-fixed text-on-surface-variant px-stack-sm py-0.5 rounded text-label-sm">{escape(category)}</span>
  </td>
  <td class="px-margin-mobile py-stack-md max-w-xs">
    <a href="{escape(link)}" class="text-body-md text-on-surface-variant hover:text-primary line-clamp-2">{escape(query[:70])}</a>
  </td>
  <td class="px-margin-mobile py-stack-md">
    <div class="flex items-center gap-base"><span class="w-2 h-2 rounded-full {dot}"></span><span class="text-body-md {status_cls}">{status}</span></div>
  </td>
  <td class="px-margin-mobile py-stack-md font-data-tabular text-on-surface-variant">{escape(str(score))}</td>
</tr>"""


def _smoke_table_rows(smoke: dict[str, Any]) -> str:
    rows = []
    for c in smoke.get("cases") or []:
        q = str(c.get("query") or "")
        ok = bool((c.get("search") or {}).get("ok"))
        score = (c.get("search") or {}).get("top_score", "—")
        rows.append(
            _status_row(
                str(c.get("id") or "—"),
                str(c.get("category") or "—"),
                q,
                ok,
                f"{score}" if score != "—" else "—",
                link=_href("search.html", q),
            )
        )
    return "".join(rows) or '<tr><td colspan="5" class="px-margin-mobile py-stack-lg text-on-surface-variant">Sin query-smoke.json</td></tr>'


def _validation_table_rows(rag_val: dict[str, Any], limit: int = 10) -> str:
    rows = []
    for c in (rag_val.get("cases") or [])[:limit]:
        q = str(c.get("query") or "")
        ok = bool((c.get("search") or {}).get("ok"))
        rows.append(
            _status_row(
                str(c.get("id") or "—"),
                str(c.get("category") or "—"),
                q,
                ok,
                "—",
                link=_href("search.html", q),
            )
        )
    return "".join(rows) or '<tr><td colspan="5" class="px-margin-mobile py-stack-lg text-on-surface-variant">Sin rag-validation.json</td></tr>'


def _data_table(title: str, subtitle: str, thead: str, tbody: str, footer: str = "") -> str:
    return f"""
<div class="bg-surface-container-lowest rounded-xl border border-outline/30 shadow-sm overflow-hidden">
  <div class="p-margin-mobile border-b border-outline/20">
    <h2 class="text-headline-md font-semibold text-primary">{escape(title)}</h2>
    <p class="text-body-md text-on-surface-variant">{escape(subtitle)}</p>
  </div>
  <div class="overflow-x-auto">
    <table class="w-full text-left border-collapse">
      <thead><tr class="bg-surface-container-low">{thead}</tr></thead>
      <tbody class="divide-y divide-outline/20">{tbody}</tbody>
    </table>
  </div>
  {footer}
</div>"""


def _th(label: str) -> str:
    return (
        f'<th class="px-margin-mobile py-stack-md text-label-sm text-on-surface-variant uppercase tracking-wider '
        f'border-b border-outline/30">{escape(label)}</th>'
    )


def _ejemplo_card(cat: dict[str, Any]) -> str:
    chips = []
    for ex in cat.get("examples") or ():
        search_only = ex.get("action") == "search"
        page = "search.html" if search_only else "rag.html"
        chip_cls = (
            "bg-green-50 text-green-900 border-green-200"
            if search_only
            else "bg-primary-fixed/30 text-primary border-primary-fixed"
        )
        chips.append(
            f'<a href="{_href(page, ex["query"])}" class="inline-flex items-center px-stack-sm py-1 rounded-lg border text-label-sm font-semibold {chip_cls} hover:opacity-90 transition-opacity">{escape(ex["label"])}</a>'
        )
    return f"""
<article class="bg-surface-container-lowest p-stack-lg rounded-xl border border-outline/20 shadow-sm hover:shadow-md transition-shadow">
  <div class="flex items-start gap-stack-md mb-stack-md">
    <div class="w-10 h-10 rounded-xl bg-primary-fixed flex items-center justify-center text-on-primary-fixed font-bold text-label-sm shrink-0">{escape(str(cat.get("icon", "?")))}</div>
    <div>
      <h3 class="text-body-lg font-bold text-primary">{escape(cat.get("title", ""))}</h3>
      <p class="text-label-sm text-on-surface-variant">{escape(cat.get("tag", ""))}</p>
    </div>
  </div>
  <p class="text-body-md text-on-surface-variant mb-stack-md">{escape(cat.get("note") or "")}</p>
  <div class="flex flex-wrap gap-stack-sm">{"".join(chips)}</div>
</article>"""


def render_vitrina_index(report: dict[str, Any]) -> str:
    corpus = report.get("corpus") or {}
    smoke_s = (report.get("smoke") or {}).get("summary") or {}
    golden_s = (report.get("golden") or {}).get("summary") or {}
    rag_s = (report.get("rag_validation") or {}).get("summary") or {}
    smoke_txt, _, smoke_ok = _fmt_pass(smoke_s)
    rag_txt, _, _ = _fmt_pass(rag_s)
    mrr = golden_s.get("mrr")
    mrr_txt = f"{float(mrr):.2f}" if isinstance(mrr, (int, float)) else "—"
    docs = corpus.get("docs") or "—"
    lote = str(corpus.get("lote") or "ODS1")
    recall5 = golden_s.get("recall@5")
    recall_txt = f"{float(recall5):.0%}" if isinstance(recall5, (int, float)) and recall5 <= 1 else str(recall5 or "—")

    metrics = f"""
<div class="grid grid-cols-1 md:grid-cols-3 gap-gutter">
  {metric_card(icon="folder_open", badge="CORPUS", title="Documentos indexados", value=str(docs), subtitle="en Qdrant + Supabase", icon_bg="bg-secondary-fixed", icon_color="text-on-secondary-fixed")}
  {metric_card(icon="science", badge="SMOKE", title="Pruebas rápidas", value=smoke_txt, subtitle="consultas ancla OK" if smoke_ok else "revisar pruebas", icon_bg="bg-primary-fixed", icon_color="text-on-primary-fixed", value_color="text-primary" if smoke_ok else "text-error")}
  {metric_card(icon="insights", badge="GOLDEN", title="Calidad recuperación", value=mrr_txt, subtitle=f"recall@5 {recall_txt}", progress_pct=int(float(mrr) * 100) if isinstance(mrr, (int, float)) and mrr <= 1 else None)}
</div>"""

    notice = """
<div class="bg-primary text-on-primary p-stack-lg rounded-xl relative overflow-hidden">
  <div class="relative z-10 max-w-3xl">
    <h2 class="text-headline-md font-semibold mb-stack-sm">Memoria técnica indexada</h2>
    <p class="text-body-md opacity-90">La ingesta es gestionada internamente por Monitoring. Esta vitrina muestra resultados de pruebas y permite consultas de ejemplo sobre el índice activo.</p>
  </div>
  <div class="absolute -bottom-8 -right-8 w-32 h-32 bg-primary-container rounded-full opacity-30 blur-2xl"></div>
</div>"""

    thead = "".join(_th(x) for x in ("Caso", "Categoría", "Consulta", "Estado", "Score"))
    activity = _data_table(
        "Pruebas smoke recientes",
        "Validación de búsqueda híbrida — clic para probar en vivo",
        thead,
        _smoke_table_rows(report.get("smoke") or {}),
        footer=f'<div class="p-stack-md bg-surface-container-low border-t border-outline/20 text-label-sm text-on-surface-variant">Validación RAG: {escape(rag_txt)} · <a href="{_href("pruebas.html")}" class="text-primary font-semibold">Ver informe completo →</a></div>',
    )

    quick = f"""
<div class="grid grid-cols-1 lg:grid-cols-3 gap-gutter">
  <a href="{_href('ejemplos.html')}" class="lg:col-span-2 bg-surface-container-lowest p-stack-lg rounded-xl border border-outline/20 shadow-sm hover:border-primary transition-colors block">
    <h3 class="text-body-lg font-bold text-primary mb-stack-sm">Ejemplos de consulta</h3>
    <p class="text-body-md text-on-surface-variant mb-stack-md">NCC-030 · FMECA · GUIGS · matrices MRI — un clic abre búsqueda o RAG con citas.</p>
    <span class="inline-flex items-center gap-base text-secondary font-semibold text-label-sm">Explorar ejemplos <span class="material-symbols-outlined text-base">arrow_forward</span></span>
  </a>
  <div class="bg-secondary-container text-on-secondary-container p-stack-lg rounded-xl flex flex-col justify-between">
    <div>
      <h3 class="text-headline-md font-semibold mb-stack-sm">Consulta libre</h3>
      <p class="text-body-md opacity-90">Escriba su pregunta. Revise siempre las citas documentales.</p>
    </div>
    <a href="{_href('rag.html')}" class="mt-stack-md w-full py-stack-md bg-primary text-on-primary rounded-lg text-label-sm font-bold uppercase tracking-wider text-center hover:opacity-95 transition-opacity">Abrir Consulta RAG</a>
  </div>
</div>"""

    steps = """
<div class="bg-surface-container-lowest rounded-xl border border-outline/20 p-stack-lg">
  <h2 class="text-headline-md font-semibold text-primary mb-stack-md">Cómo usar</h2>
  <ol class="space-y-stack-md text-body-md text-on-surface-variant list-decimal list-inside">
    <li><strong class="text-on-surface">Revise las pruebas</strong> — confirme smoke y golden set.</li>
    <li><strong class="text-on-surface">Elija un ejemplo</strong> — o use Búsqueda / Consulta RAG.</li>
    <li><strong class="text-on-surface">Verifique la cita</strong> — el documento fuente es la evidencia.</li>
  </ol>
</div>"""

    content = notice + metrics + activity + quick + steps
    return render_shell(
        active="home",
        title="Dashboard MMI",
        header_subtitle=f"Corpus {lote} · {docs} documentos",
        content=content,
        corpus_lote=lote,
    )


def render_pruebas_html(report: dict[str, Any]) -> str:
    corpus = report.get("corpus") or {}
    smoke = report.get("smoke") or {}
    golden = report.get("golden") or {}
    rag_val = report.get("rag_validation") or {}
    golden_sum = golden.get("summary") or {}
    lote = str(corpus.get("lote") or "ODS1")
    p95 = report.get("load_test_p95_ms")
    p95_txt = f"{p95:.0f} ms" if isinstance(p95, (int, float)) else "—"

    metrics = f"""
<div class="grid grid-cols-2 md:grid-cols-4 gap-gutter">
  {metric_card(icon="science", badge="SMOKE", title="Smoke test", value=_fmt_pass(smoke.get("summary"))[0], subtitle="búsqueda híbrida", icon_bg="bg-primary-fixed", icon_color="text-on-primary-fixed")}
  {metric_card(icon="star", badge="GOLDEN", title="MRR", value=str(golden_sum.get("mrr", "—")), subtitle=f"{golden.get('case_count', '—')} casos")}
  {metric_card(icon="check_circle", badge="RAG", title="Validación", value=_fmt_pass(rag_val.get("summary"))[0], subtitle="batería ampliada", icon_bg="bg-secondary-fixed", icon_color="text-on-secondary-fixed")}
  {metric_card(icon="speed", badge="CARGA", title="Latencia p95", value=p95_txt, subtitle="búsqueda directa")}
</div>"""

    smoke_table = _data_table(
        "Smoke test",
        f"Generado {(smoke.get('generated_at') or '')[:10]}",
        "".join(_th(x) for x in ("Caso", "Categoría", "Consulta", "Estado", "Score")),
        _smoke_table_rows(smoke),
    )

    golden_rows = "".join(
        f'<tr class="border-b border-outline/10"><td class="px-margin-mobile py-stack-sm text-on-surface-variant">{escape(k)}</td><td class="px-margin-mobile py-stack-sm font-semibold text-primary">{escape(str(golden_sum.get(k, "—")))}</td></tr>'
        for k in ("mrr", "recall@1", "recall@5", "recall@8")
    )
    golden_block = f"""
<div class="bg-surface-container-lowest rounded-xl border border-outline/20 p-stack-lg">
  <h2 class="text-headline-md font-semibold text-primary mb-stack-md">Golden set</h2>
  <table class="w-full"><tbody>{golden_rows}</tbody></table>
</div>"""

    rag_table = _data_table(
        "Validación RAG",
        f"Generado {(rag_val.get('generated_at') or '')[:10]}",
        "".join(_th(x) for x in ("Caso", "Categoría", "Consulta", "Estado", "Score")),
        _validation_table_rows(rag_val),
    )

    content = metrics + smoke_table + golden_block + rag_table
    return render_shell(
        active="pruebas",
        title="Resultados de pruebas",
        header_subtitle=f"Informe estático · {report.get('generated_at', '')[:10]}",
        content=content,
        corpus_lote=lote,
    )


def render_ejemplos_html(out_dir: Path | None = None) -> str:
    stats = load_corpus_stats(out_dir)
    docs = stats.get("docs") or "—"
    lote = str(stats.get("lote") or "ODS1")
    cards = "".join(_ejemplo_card(c) for c in _CATEGORIES)
    tips = "".join(_ejemplo_card(c) for c in _TIPS)

    content = f"""
<div class="bg-surface-container-low p-stack-md rounded-xl border border-outline/20 text-body-md text-on-surface-variant">
  <strong class="text-primary">{docs}</strong> documentos indexados · clic azul = <strong>Consulta RAG</strong> · clic verde = <strong>solo búsqueda</strong>
</div>
<div>
  <h2 class="text-headline-md font-semibold text-primary mb-stack-md">Corpus ODS1</h2>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-gutter">{cards}</div>
</div>
<div>
  <h2 class="text-headline-md font-semibold text-primary mb-stack-md">Consejos de consulta</h2>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-gutter">{tips}</div>
</div>"""

    return render_shell(
        active="ejemplos",
        title="Ejemplos de consulta",
        header_subtitle="Consultas predefinidas del corpus",
        content=content,
        corpus_lote=lote,
    )


def write_vitrina_pages(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    from mmi.web.sync import sync_web_assets

    sync_web_assets(out_dir)
    prev_mode = os.environ.get("MMI_DEPLOY_MODE")
    os.environ["MMI_DEPLOY_MODE"] = "vitrina"
    try:
        report = build_pruebas_report(out_dir)

        paths: dict[str, Path] = {
            "index": out_dir / "index.html",
            "pruebas": out_dir / "pruebas.html",
            "ejemplos": out_dir / "ejemplos.html",
            "search": out_dir / "search.html",
            "rag": out_dir / "rag.html",
            "robots": out_dir / "robots.txt",
            "json": out_dir / "vitrina-report.json",
        }
        paths["index"].write_text(render_vitrina_index(report), encoding="utf-8")
        paths["pruebas"].write_text(render_pruebas_html(report), encoding="utf-8")
        paths["ejemplos"].write_text(render_ejemplos_html(out_dir), encoding="utf-8")
        paths["robots"].write_text(VITRINA_ROBOTS, encoding="utf-8")
        paths["json"].write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        from mmi.search.rag_page import render_rag_html
        from mmi.tools.search_cli import render_search_html

        paths["search"].write_text(render_search_html(out_dir), encoding="utf-8")
        paths["rag"].write_text(render_rag_html(out_dir), encoding="utf-8")
        return paths
    finally:
        if prev_mode is None:
            os.environ.pop("MMI_DEPLOY_MODE", None)
        else:
            os.environ["MMI_DEPLOY_MODE"] = prev_mode
