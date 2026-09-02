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

# Credenciales demo de la vitrina (también default en deploy/entrypoint.sh en Railway).
DEMO_AUTH_USER = "Prueba Monitoring"
DEMO_AUTH_PASSWORD = "202608v1"

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
            "bg-green-50 text-green-900 border-green-200 hover:bg-green-100"
            if search_only
            else "bg-primary-fixed/30 text-primary border-primary-fixed hover:bg-primary-fixed/50"
        )
        mode_label = "solo búsqueda" if search_only else "Consulta RAG"
        chips.append(
            f'<button type="button" data-ejemplo-go data-page="{escape(page)}" '
            f'data-q="{escape(ex["query"], quote=True)}" '
            f'title="{escape(ex["query"])} · {escape(mode_label)}" '
            f'class="inline-flex items-center px-stack-sm py-1 rounded-lg border text-label-sm font-semibold {chip_cls} transition-colors">'
            f"{escape(ex['label'])}</button>"
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

    p95 = report.get("load_test_p95_ms")
    p95_txt = f"{float(p95):.0f} ms" if isinstance(p95, (int, float)) else "—"
    golden_cases = (report.get("golden") or {}).get("case_count") or "—"

    metrics = f"""
<div class="grid grid-cols-1 md:grid-cols-3 gap-gutter">
  {metric_card(icon="folder_open", badge="CORPUS", title="Documentos indexados", value=str(docs), subtitle="en Qdrant + Supabase", icon_bg="bg-secondary-fixed", icon_color="text-on-secondary-fixed")}
  {metric_card(icon="science", badge="SMOKE", title="Pruebas rápidas", value=smoke_txt, subtitle="consultas ancla OK" if smoke_ok else "revisar pruebas", icon_bg="bg-primary-fixed", icon_color="text-on-primary-fixed", value_color="text-primary" if smoke_ok else "text-error")}
  {metric_card(icon="insights", badge="GOLDEN", title="Calidad recuperación", value=mrr_txt, subtitle=f"recall@5 {recall_txt}", progress_pct=int(float(mrr) * 100) if isinstance(mrr, (int, float)) and mrr <= 1 else None)}
</div>"""

    notice = f"""
<div class="bg-primary text-on-primary p-stack-lg rounded-xl relative overflow-hidden">
  <div class="relative z-10 max-w-3xl">
    <p class="text-label-sm uppercase tracking-wider opacity-80 mb-base">Proyecto de análisis</p>
    <h2 class="text-headline-md font-semibold mb-stack-sm">{escape(PROJECT_NAME)}</h2>
    <p class="text-body-md opacity-90 mb-stack-md">Esta vitrina corresponde al análisis documental del servicio de estudio de mantenibilidad y confiabilidad (M&amp;C) del sistema de enfriamiento DCH. Muestra resultados de pruebas y consultas sobre el corpus indexado · lote {escape(lote)} · {escape(str(docs))} documentos.</p>
    <button type="button" id="guide-open" class="inline-flex items-center gap-stack-sm bg-on-primary text-primary px-stack-md py-stack-sm rounded-lg text-label-sm font-bold uppercase tracking-wider hover:opacity-95 transition-opacity shadow-sm">
      <span class="material-symbols-outlined" style="font-size:18px">menu_book</span>
      Significados y logros
    </button>
  </div>
  <div class="absolute -bottom-8 -right-8 w-32 h-32 bg-primary-container rounded-full opacity-30 blur-2xl"></div>
</div>

<div class="bg-surface-container-lowest rounded-xl border border-outline/20 p-stack-lg shadow-sm">
  <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-stack-md">
    <div class="flex items-start gap-stack-md min-w-0">
      <div class="p-stack-sm bg-secondary-fixed rounded-xl text-on-secondary-fixed shrink-0">
        <span class="material-symbols-outlined">key</span>
      </div>
      <div>
        <p class="text-label-sm font-bold uppercase tracking-wider text-on-surface-variant mb-base">Acceso demo</p>
        <p class="text-body-md text-on-surface-variant">El navegador pedirá estas credenciales para consultar el corpus (búsqueda y RAG).</p>
      </div>
    </div>
    <dl class="grid grid-cols-1 sm:grid-cols-2 gap-stack-sm sm:gap-stack-md shrink-0 w-full sm:w-auto">
      <div class="rounded-lg bg-surface-container-low border border-outline/15 px-stack-md py-stack-sm">
        <dt class="text-label-sm uppercase tracking-wider text-on-surface-variant">Usuario</dt>
        <dd class="text-body-lg font-semibold text-primary font-data-tabular break-all">{escape(DEMO_AUTH_USER)}</dd>
      </div>
      <div class="rounded-lg bg-surface-container-low border border-outline/15 px-stack-md py-stack-sm">
        <dt class="text-label-sm uppercase tracking-wider text-on-surface-variant">Contraseña</dt>
        <dd class="text-body-lg font-semibold text-primary font-data-tabular">{escape(DEMO_AUTH_PASSWORD)}</dd>
      </div>
    </dl>
  </div>
</div>

<dialog id="guide-dialog" class="guide-dialog w-[min(92vw,40rem)] max-h-[85vh] rounded-xl border border-outline/20 bg-surface-container-lowest p-0 shadow-xl backdrop:bg-primary/40 backdrop:backdrop-blur-sm open:flex open:flex-col">
  <div class="flex items-start justify-between gap-stack-md p-stack-lg border-b border-outline/15 bg-surface">
    <div>
      <p class="text-label-sm uppercase tracking-wider text-on-surface-variant mb-base">Guía rápida</p>
      <h2 class="text-headline-md font-semibold text-primary">Qué es esto y qué logramos</h2>
      <p class="text-body-md text-on-surface-variant mt-base">{escape(PROJECT_SHORT)} · lote {escape(lote)}</p>
    </div>
    <button type="button" id="guide-close" class="shrink-0 w-10 h-10 rounded-lg bg-surface-container-low text-on-surface-variant hover:text-primary hover:bg-surface-container transition-colors flex items-center justify-center" aria-label="Cerrar">
      <span class="material-symbols-outlined">close</span>
    </button>
  </div>
  <div class="overflow-y-auto p-stack-lg space-y-stack-md flex-1">
    <details class="metric-explain group bg-surface-container-low rounded-xl border border-outline/15 open:border-primary/30 open:bg-primary-fixed/20" open>
      <summary class="list-none cursor-pointer flex items-center justify-between gap-stack-sm px-stack-md py-stack-md select-none">
        <span class="inline-flex items-center gap-stack-sm text-body-lg font-semibold text-primary">
          <span class="material-symbols-outlined text-secondary">flag</span>
          Qué es esta vitrina
        </span>
        <span class="material-symbols-outlined text-outline group-open:rotate-180 transition-transform">expand_more</span>
      </summary>
      <div class="px-stack-md pb-stack-md text-body-md text-on-surface-variant leading-relaxed space-y-stack-sm">
        <p>MMI (Monitoring Document Intelligence) indexa el corpus del estudio M&amp;C del sistema de enfriamiento DCH y permite <strong class="text-on-surface">buscar</strong> y <strong class="text-on-surface">consultar con RAG</strong> (respuesta con citas al documento fuente).</p>
        <p>Esta web es una <strong class="text-on-surface">vitrina operativa</strong>: muestra calidad de recuperación y ejemplos listos, sin herramientas de ingesta ni revisión interna.</p>
      </div>
    </details>

    <details class="metric-explain group bg-surface-container-low rounded-xl border border-outline/15 open:border-primary/30">
      <summary class="list-none cursor-pointer flex items-center justify-between gap-stack-sm px-stack-md py-stack-md select-none">
        <span class="inline-flex items-center gap-stack-sm text-body-lg font-semibold text-primary">
          <span class="material-symbols-outlined text-secondary">dictionary</span>
          Significados
        </span>
        <span class="material-symbols-outlined text-outline group-open:rotate-180 transition-transform">expand_more</span>
      </summary>
      <dl class="px-stack-md pb-stack-md space-y-stack-md text-body-md text-on-surface-variant">
        <div>
          <dt class="font-semibold text-on-surface">Corpus</dt>
          <dd>Documentos del proyecto ya chunked e indexados en Qdrant (vectores) + Supabase (metadatos / FTS).</dd>
        </div>
        <div>
          <dt class="font-semibold text-on-surface">Smoke</dt>
          <dd>Prueba rápida de humo: pocas consultas ancla (códigos, normas, equipos). Si pasan, la búsqueda híbrida está viva.</dd>
        </div>
        <div>
          <dt class="font-semibold text-on-surface">Golden / MRR</dt>
          <dd>Set dorado de consultas con respuesta esperada. MRR (Mean Reciprocal Rank) mide qué tan arriba aparece el documento correcto (cerca de 1.0 = excelente).</dd>
        </div>
        <div>
          <dt class="font-semibold text-on-surface">Recall@5</dt>
          <dd>Proporción de casos en que el documento correcto está entre los 5 primeros resultados.</dd>
        </div>
        <div>
          <dt class="font-semibold text-on-surface">RAG</dt>
          <dd>Retrieval-Augmented Generation: el modelo responde usando fragmentos recuperados y debe citar la evidencia.</dd>
        </div>
        <div>
          <dt class="font-semibold text-on-surface">Latencia p95</dt>
          <dd>En prueba de carga, el 95 % de las búsquedas respondió en ese tiempo o menos.</dd>
        </div>
      </dl>
    </details>

    <details class="metric-explain group bg-surface-container-low rounded-xl border border-outline/15 open:border-primary/30">
      <summary class="list-none cursor-pointer flex items-center justify-between gap-stack-sm px-stack-md py-stack-md select-none">
        <span class="inline-flex items-center gap-stack-sm text-body-lg font-semibold text-primary">
          <span class="material-symbols-outlined text-secondary">emoji_events</span>
          Lo que logramos
        </span>
        <span class="material-symbols-outlined text-outline group-open:rotate-180 transition-transform">expand_more</span>
      </summary>
      <ul class="px-stack-md pb-stack-md space-y-stack-sm text-body-md text-on-surface-variant list-none">
        <li class="flex gap-stack-sm"><span class="material-symbols-outlined text-primary shrink-0" style="font-size:20px">check_circle</span><span><strong class="text-on-surface">{escape(str(docs))} documentos</strong> indexados del lote {escape(lote)} (Qdrant + Supabase).</span></li>
        <li class="flex gap-stack-sm"><span class="material-symbols-outlined text-primary shrink-0" style="font-size:20px">check_circle</span><span><strong class="text-on-surface">Smoke {escape(smoke_txt)}</strong> — consultas ancla de búsqueda híbrida en verde.</span></li>
        <li class="flex gap-stack-sm"><span class="material-symbols-outlined text-primary shrink-0" style="font-size:20px">check_circle</span><span><strong class="text-on-surface">MRR {escape(mrr_txt)}</strong> y recall@5 {escape(recall_txt)} sobre {escape(str(golden_cases))} casos golden.</span></li>
        <li class="flex gap-stack-sm"><span class="material-symbols-outlined text-primary shrink-0" style="font-size:20px">check_circle</span><span><strong class="text-on-surface">Validación RAG {escape(rag_txt)}</strong> — batería ampliada con citas.</span></li>
        <li class="flex gap-stack-sm"><span class="material-symbols-outlined text-primary shrink-0" style="font-size:20px">check_circle</span><span><strong class="text-on-surface">Latencia p95 {escape(p95_txt)}</strong> en búsqueda directa (referencia de carga).</span></li>
        <li class="flex gap-stack-sm"><span class="material-symbols-outlined text-primary shrink-0" style="font-size:20px">check_circle</span><span>Vitrina pública con ejemplos, búsqueda y consulta RAG listos para demostrar el análisis M&amp;C · Enfriamiento DCH.</span></li>
      </ul>
    </details>
  </div>
  <div class="p-stack-md border-t border-outline/15 bg-surface flex flex-wrap gap-stack-sm justify-end">
    <a href="{_href('pruebas.html')}" class="px-stack-md py-stack-sm rounded-lg text-label-sm font-semibold text-primary hover:bg-primary-fixed/40 transition-colors">Ver pruebas</a>
    <button type="button" id="guide-close-2" class="px-stack-md py-stack-sm rounded-lg bg-primary text-on-primary text-label-sm font-bold uppercase tracking-wider hover:opacity-95 transition-opacity">Entendido</button>
  </div>
</dialog>"""

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
    guide_script = """
<script>
(function () {
  var dlg = document.getElementById('guide-dialog');
  if (!dlg) return;
  function openGuide() { if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', ''); }
  function closeGuide() { if (typeof dlg.close === 'function') dlg.close(); else dlg.removeAttribute('open'); }
  var openBtn = document.getElementById('guide-open');
  if (openBtn) openBtn.addEventListener('click', openGuide);
  ['guide-close', 'guide-close-2'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('click', closeGuide);
  });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) closeGuide(); });
})();
</script>"""
    return render_shell(
        active="home",
        title="Dashboard MMI",
        header_subtitle=f"{PROJECT_SHORT} · lote {lote} · {docs} documentos",
        content=content,
        corpus_lote=PROJECT_SHORT,
        footer_scripts=guide_script,
        extra_head="""
<style>
  dialog.guide-dialog::backdrop { background: rgba(11, 37, 69, 0.45); backdrop-filter: blur(2px); }
  dialog.guide-dialog[open] { display: flex; flex-direction: column; margin: auto; }
</style>""",
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
<div class="bg-surface-container-low p-stack-md rounded-xl border border-outline/20 text-body-md text-on-surface-variant mb-gutter">
  Indicadores del análisis <strong class="text-primary">{escape(PROJECT_SHORT)}</strong>.
  Pulse <strong class="text-on-surface">¿Qué significa?</strong> en cada tarjeta para la definición.
</div>
<div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-gutter">
  {metric_card(
      icon="science",
      badge="SMOKE",
      title="Smoke test",
      value=_fmt_pass(smoke.get("summary"))[0],
      subtitle="búsqueda híbrida",
      icon_bg="bg-primary-fixed",
      icon_color="text-on-primary-fixed",
      explanation=(
          "Prueba rápida de humo: consultas ancla del proyecto (códigos, normas, equipos). "
          "3/3 indica que la búsqueda híbrida (Qdrant + Supabase) respondió en todos los casos críticos. "
          "Si falla alguno, el índice o la API no están listos para consulta."
      ),
  )}
  {metric_card(
      icon="star",
      badge="GOLDEN",
      title="MRR",
      value=str(golden_sum.get("mrr", "—")),
      subtitle=f"{golden.get('case_count', '—')} casos",
      explanation=(
          "Mean Reciprocal Rank: calidad de recuperación sobre un set dorado de consultas con respuesta esperada. "
          "Valor cerca de 1.0 = el documento correcto aparece muy arriba en los resultados. "
          "0.91 en ~35 casos indica buen ranking para el corpus M&C · Enfriamiento DCH. "
          "Complementa recall@1 / @5 / @8 en la tabla Golden set."
      ),
  )}
  {metric_card(
      icon="check_circle",
      badge="RAG",
      title="Validación",
      value=_fmt_pass(rag_val.get("summary"))[0],
      subtitle="batería ampliada",
      icon_bg="bg-secondary-fixed",
      icon_color="text-on-secondary-fixed",
      explanation=(
          "Batería de validación RAG: el sistema genera respuesta con citas y se comprueba que use evidencia del corpus. "
          "10/10 = todas las preguntas de la suite pasaron (citación y coherencia mínima). "
          "No sustituye revisión humana: siempre verifique el documento fuente."
      ),
  )}
  {metric_card(
      icon="speed",
      badge="CARGA",
      title="Latencia p95",
      value=p95_txt,
      subtitle="búsqueda directa",
      explanation=(
          "Percentil 95 de latencia en prueba de carga de búsqueda directa: "
          "el 95 % de las consultas respondió en este tiempo o menos. "
          "Valores altos (varios segundos) pueden deberse a red, embeddings o cold start; "
          "úselo para comparar despliegues, no como SLA contractual."
      ),
  )}
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
        header_subtitle=f"{PROJECT_SHORT} · informe {report.get('generated_at', '')[:10]}",
        content=content,
        corpus_lote=PROJECT_SHORT,
    )


def render_ejemplos_html(out_dir: Path | None = None) -> str:
    stats = load_corpus_stats(out_dir)
    docs = stats.get("docs") or "—"
    lote = str(stats.get("lote") or "ODS1")
    cards = "".join(_ejemplo_card(c) for c in _CATEGORIES)
    tips = "".join(_ejemplo_card(c) for c in _TIPS)

    content = f"""
<div class="bg-surface-container-lowest rounded-xl border border-outline/20 p-stack-lg shadow-sm">
  <div class="flex items-start gap-stack-md">
    <div class="p-stack-sm bg-primary-fixed rounded-xl text-on-primary-fixed shrink-0">
      <span class="material-symbols-outlined">touch_app</span>
    </div>
    <div class="min-w-0 space-y-stack-sm">
      <h2 class="text-headline-md font-semibold text-primary">Qué pasa al pulsar un ejemplo</h2>
      <p class="text-body-md text-on-surface-variant">
        Corpus: <strong class="text-primary">{escape(str(docs))}</strong> documentos · lote {escape(lote)}.
        Elija un chip; verá <strong class="text-on-surface">Analizando…</strong> unos segundos y luego el resultado.
      </p>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-stack-md pt-stack-sm">
        <div class="rounded-lg border border-primary-fixed bg-primary-fixed/20 p-stack-md">
          <p class="text-label-sm font-bold uppercase tracking-wider text-primary mb-base">Chip azul</p>
          <p class="text-body-md text-on-surface-variant">Abre <strong class="text-on-surface">Consulta RAG</strong>: recupera evidencia del corpus, genera respuesta con citas y muestra referencias. Puede tardar varios segundos — no cierre la pestaña.</p>
        </div>
        <div class="rounded-lg border border-green-200 bg-green-50 p-stack-md">
          <p class="text-label-sm font-bold uppercase tracking-wider text-green-900 mb-base">Chip verde</p>
          <p class="text-body-md text-green-900/80">Abre <strong class="text-green-950">solo búsqueda</strong>: lista fragmentos híbridos (Qdrant + Supabase) sin generar texto. Más rápido, sin respuesta narrativa.</p>
        </div>
      </div>
    </div>
  </div>
</div>
<div>
  <h2 class="text-headline-md font-semibold text-primary mb-stack-md">Corpus del proyecto</h2>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-gutter">{cards}</div>
</div>
<div>
  <h2 class="text-headline-md font-semibold text-primary mb-stack-md">Consejos de consulta</h2>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-gutter">{tips}</div>
</div>
<div id="analyzing-overlay" class="fixed inset-0 z-[100] hidden items-center justify-center bg-primary/50 backdrop-blur-sm p-margin-mobile" aria-live="polite" aria-busy="true">
  <div class="w-full max-w-md bg-surface-container-lowest rounded-xl border border-outline/20 shadow-xl p-stack-lg text-center">
    <div class="mx-auto mb-stack-md w-14 h-14 rounded-full bg-primary-fixed flex items-center justify-center text-on-primary-fixed animate-pulse">
      <span class="material-symbols-outlined" style="font-size:28px">hourglass_top</span>
    </div>
    <p id="analyzing-title" class="text-headline-md font-semibold text-primary mb-stack-sm">Analizando…</p>
    <p id="analyzing-sub" class="text-body-md text-on-surface-variant">Preparando la consulta. Espere un momento.</p>
    <div class="mt-stack-md h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
      <div class="h-full bg-primary rounded-full animate-pulse" style="width:70%"></div>
    </div>
  </div>
</div>"""

    scripts = """
<script>
(function () {
  var overlay = document.getElementById('analyzing-overlay');
  var titleEl = document.getElementById('analyzing-title');
  var subEl = document.getElementById('analyzing-sub');
  var DELAY_MS = 1600;

  function showAnalyzing(isSearch, query) {
    if (!overlay) return;
    titleEl.textContent = 'Analizando…';
    subEl.textContent = isSearch
      ? 'Búsqueda híbrida de fragmentos. Espere…'
      : 'Consulta RAG con citas. Esto puede tardar varios segundos…';
    overlay.classList.remove('hidden');
    overlay.classList.add('flex');
  }

  document.querySelectorAll('[data-ejemplo-go]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var page = btn.getAttribute('data-page') || 'rag.html';
      var query = btn.getAttribute('data-q') || '';
      if (!query) return;
      var isSearch = page.indexOf('search') === 0;
      showAnalyzing(isSearch, query);
      btn.disabled = true;
      setTimeout(function () {
        location.href = '/' + page + '?q=' + encodeURIComponent(query);
      }, DELAY_MS);
    });
  });
})();
</script>"""

    return render_shell(
        active="ejemplos",
        title="Ejemplos de consulta",
        header_subtitle=f"{PROJECT_SHORT} · consultas predefinidas",
        content=content,
        corpus_lote=PROJECT_SHORT,
        footer_scripts=scripts,
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
