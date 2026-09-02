"""Informe unificado de resultados de ingesta (Fase 0 + indice + volumenes)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from mmi.analysis.data_report import (
    _coverage_by_folder,
    _load_json,
    _phase0_by_extension,
    _planos_by_subdir,
    _reject_reasons,
    _status_by_tipo,
)
from mmi.analysis.ocr_status import ocr_staging_summary
from mmi.analysis.status import load_token_summary
from mmi.index.ingestion_registry import load_registry


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def _ocr_pages_estimate(out_dir: Path, plan_scan: dict[str, Any] | None) -> dict[str, Any]:
    staging = ocr_staging_summary(out_dir)
    staged_pages = sum(int(d.get("page_count") or 0) for d in staging.get("documents") or [])
    pilot = _load_json(out_dir / "ocr-pilot-summary.json") or {}
    pilot_pages = int((pilot.get("ocr") or {}).get("page_count") or 0)

    plano_pages = 0
    plano_candidates = 0
    if isinstance(plan_scan, dict):
        plano_candidates = int(plan_scan.get("planos") or 0)
        for row in plan_scan.get("plano_candidates") or []:
            plano_pages += int(row.get("pages_needs_ocr") or row.get("page_count") or 0)

    return {
        "staged_documents": staging.get("count", 0),
        "staged_pages_processed": staged_pages,
        "pilot_pages": pilot_pages,
        "planos_detected": plano_candidates,
        "planos_pages_needs_ocr": plano_pages,
        "staging_summary": staging,
    }


def _index_rows(out_dir: Path) -> list[dict[str, Any]]:
    raw = _load_json(out_dir / "index-corpus-summary.json")
    if not isinstance(raw, dict):
        return []
    rows = []
    for r in raw.get("results") or []:
        rows.append(
            {
                "archivo": r.get("archivo", ""),
                "estado": r.get("estado", ""),
                "chunks": int(r.get("chunks") or 0),
                "tokens": int(r.get("tokens") or 0),
                "document_id": r.get("document_id", ""),
                "document_key": r.get("document_key", ""),
                "sha256": r.get("sha256", ""),
            }
        )
    rows.sort(key=lambda x: x.get("tokens", 0), reverse=True)
    return rows


def build_ingestion_results(out_dir: Path) -> dict[str, Any]:
    out_dir = Path(out_dir)
    status = _load_json(out_dir / "analysis-status.json") or {}
    analyses = status.get("analyses") or []
    if isinstance(analyses, dict):
        analyses = list(analyses.values())

    token_summary = status.get("token_summary") or load_token_summary(out_dir)
    plan_scan = _load_json(out_dir / "plan-scan.json")
    golden = _load_json(out_dir / "golden-set-eval.json")
    smoke = _load_json(out_dir / "query-smoke.json")
    rag_val = _load_json(out_dir / "rag-validation.json")
    load_test = _load_json(out_dir / "load-test-report.json")
    registry = load_registry(out_dir / "ingestion-registry.json")

    ocr = _ocr_pages_estimate(out_dir, plan_scan if isinstance(plan_scan, dict) else None)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "lote": status.get("lote"),
            "policy": status.get("policy"),
            "corpus_root": status.get("corpus_root"),
            "generated_at_status": status.get("generated_at"),
        },
        "summary": status.get("summary") or {},
        "index_summary": status.get("index_summary") or {},
        "token_summary": token_summary,
        "ocr": ocr,
        "phase0_by_extension": _phase0_by_extension(analyses),
        "status_by_tipo": _status_by_tipo(analyses),
        "coverage_by_folder": _coverage_by_folder(analyses),
        "reject_top": _reject_reasons(analyses),
        "planos": {
            "total": (plan_scan or {}).get("planos", 0) if isinstance(plan_scan, dict) else 0,
            "scanned": (plan_scan or {}).get("scanned", 0) if isinstance(plan_scan, dict) else 0,
            "by_subdir": _planos_by_subdir(plan_scan if isinstance(plan_scan, dict) else None),
        },
        "retrieval": {
            "golden": (golden or {}).get("summary") if isinstance(golden, dict) else None,
            "smoke": (smoke or {}).get("summary") if isinstance(smoke, dict) else None,
            "rag_validation": (rag_val or {}).get("summary") if isinstance(rag_val, dict) else None,
        },
        "load_test": load_test if isinstance(load_test, dict) else None,
        "registry": {
            "updated_at": registry.get("updated_at"),
            "job_count": len(registry.get("jobs") or []),
            "recent_jobs": list(reversed(registry.get("jobs") or []))[:10],
        },
        "index_top_docs": _index_rows(out_dir)[:25],
        "document_count": len(analyses),
        "sources": {
            "analysis_status": (out_dir / "analysis-status.json").exists(),
            "index_corpus_summary": (out_dir / "index-corpus-summary.json").exists(),
            "plan_scan": (out_dir / "plan-scan.json").exists(),
            "ingestion_registry": (out_dir / "ingestion-registry.json").exists(),
        },
    }


def render_ingestion_results_html(report: dict[str, Any], *, out_dir: Path | None = None) -> str:
    from mmi.analysis.review_shell import render_review_nav, review_nav_css

    cs = report.get("summary") or {}
    idx = report.get("index_summary") or {}
    tok = report.get("token_summary") or {}
    ocr = report.get("ocr") or {}
    ret = report.get("retrieval") or {}
    golden = ret.get("golden") or {}
    smoke = ret.get("smoke") or {}
    rag = ret.get("rag_validation") or {}
    registry = report.get("registry") or {}

    folder_rows = "".join(
        f"<tr><td>{escape(r['folder'])}</td><td>{r['total']}</td><td>{r['pass']}</td>"
        f"<td>{r['reject']}</td><td>{r['indexados']}</td><td>{r['index_pct']}%</td></tr>"
        for r in (report.get("coverage_by_folder") or [])[:15]
    )

    ext_rows = "".join(
        f"<tr><td>.{escape(ext)}</td>"
        + "".join(f"<td>{counts.get(s, 0)}</td>" for s in ("pass", "review", "reject", "excluido"))
        + "</tr>"
        for ext, counts in sorted((report.get("phase0_by_extension") or {}).items())
    )

    reject_rows = "".join(
        f"<tr><td>{r['count']}</td><td>{escape(r['reason'])}</td></tr>"
        for r in (report.get("reject_top") or [])[:12]
    )

    ocr_docs = (ocr.get("staging_summary") or {}).get("documents") or []
    ocr_rows = "".join(
        f"<tr><td>{escape(str(d.get('document_id', '')))}</td><td>{escape(str(d.get('quality', '')))}</td>"
        f"<td>{d.get('page_count', '—')}</td><td>{d.get('avg_confidence', '—')}</td>"
        f"<td>{escape(str(d.get('engine', '')))}</td>"
        f"<td>{('<a href=\"ocr-staging/' + escape(str(d.get('document_id', ''))) + '/ocr-review.html\">Review</a>') if d.get('review_url') else '—'}</td></tr>"
        for d in ocr_docs
    )

    top_index = "".join(
        f"<tr><td>{escape(r.get('archivo', ''))}</td><td>{escape(str(r.get('estado', '')))}</td>"
        f"<td>{r.get('chunks', 0)}</td><td>{_fmt_tokens(int(r.get('tokens') or 0))}</td></tr>"
        for r in (report.get("index_top_docs") or [])
    )

    job_rows = "".join(
        f"<tr><td>{escape(str(j.get('recorded_at', ''))[:19])}</td>"
        f"<td>{escape(str(j.get('kind') or j.get('action') or 'job'))}</td>"
        f"<td class=\"muted\">{escape(str(j.get('note') or j.get('status') or ''))}</td></tr>"
        for j in (report.get("registry") or {}).get("recent_jobs") or []
    )

    smoke_pass = smoke.get("passed") if smoke else "—"
    smoke_total = smoke.get("total") if smoke else "—"
    rag_ok = rag.get("ask_ok") if rag else "—"
    rag_total = rag.get("total") if rag else "—"
    golden_mrr = golden.get("mrr", "—")
    golden_recall = golden.get("recall@5", golden.get("recall_at_5", "—"))
    reject_count = sum(r.get("count", 0) for r in (report.get("reject_top") or []))

    return f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MMI — Resultados de ingesta</title>
<style>
{review_nav_css()}
body {{ font-family: "Segoe UI", system-ui, sans-serif; margin: 0; padding: 20px 24px 48px; background: #0f1419; color: #e6edf3; }}
h1 {{ font-size: 1.45rem; margin: 0 0 6px; }}
h2 {{ font-size: 1.05rem; margin: 28px 0 10px; color: #b8c5d6; }}
.meta {{ color: #8b949e; font-size: 0.88rem; margin-bottom: 18px; line-height: 1.5; }}
.live-bar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding: 10px 14px; margin-bottom: 18px;
  background: #161b22; border: 1px solid #30363d; border-radius: 8px; font-size: 0.82rem; }}
.live-bar .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #3fb950; box-shadow: 0 0 8px #3fb950; }}
.stats {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 14px; min-width: 110px; }}
.card span {{ display: block; font-size: 0.72rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.04em; }}
.card b {{ display: block; font-size: 1.35rem; margin-top: 4px; }}
.card.highlight {{ border-color: #e6b84d; background: #1a1810; }}
.detail-cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin: 20px 0; }}
.detail-card {{
  background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 14px 16px; cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.1s;
}}
.detail-card:hover {{ border-color: #58a6ff88; background: #1c2128; }}
.detail-card.active {{ border-color: #58a6ff; background: #1a2332; box-shadow: 0 0 0 1px #58a6ff44; }}
.detail-card .dc-title {{ font-weight: 600; font-size: 0.92rem; margin-bottom: 6px; color: #e6edf3; }}
.detail-card .dc-kpi {{ font-size: 1.25rem; font-weight: 700; color: #58a6ff; margin-bottom: 4px; }}
.detail-card .dc-sub {{ font-size: 0.78rem; color: #8b949e; line-height: 1.4; }}
.detail-panel {{ display: none; margin-bottom: 24px; padding: 16px 18px; background: #161b22; border: 1px solid #30363d; border-radius: 10px; }}
.detail-panel.active {{ display: block; }}
.detail-panel h2 {{ margin: 0 0 12px; font-size: 1.05rem; color: #b8c5d6; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 0.82rem; }}
th, td {{ border: 1px solid #30363d; padding: 7px 9px; text-align: left; vertical-align: top; }}
th {{ background: #0d1117; position: sticky; top: 0; }}
.muted {{ color: #8b949e; font-size: 0.78rem; }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
@media (max-width: 900px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
.doc-tools {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; align-items: center; }}
.doc-tools input, .doc-tools select {{ padding: 8px 10px; border-radius: 6px; border: 1px solid #444; background: #0d1117; color: #eee; }}
.doc-table-wrap {{ max-height: 420px; overflow: auto; border: 1px solid #30363d; border-radius: 8px; }}
.links {{ margin-top: 24px; font-size: 0.82rem; }}
.links a {{ color: #58a6ff; margin-right: 14px; }}
</style></head><body>
{render_review_nav("ingestion", depth=0)}
<h1>Resultados de ingesta</h1>
<p class="meta">Generado: {escape(report.get('generated_at', ''))} · Lote: {escape(str((report.get('meta') or {}).get('lote', '—')))}<br/>
Corpus: {escape(str((report.get('meta') or {}).get('corpus_root', '')))}</p>

<div class="live-bar" id="live-bar"><span class="dot"></span><span id="live-text">Conectando actividad en vivo…</span></div>

<div class="stats">
  <div class="card"><span>Total manifest</span><b>{cs.get('total', '—')}</b></div>
  <div class="card"><span>Fase 0 pass</span><b>{cs.get('pass', '—')}</b></div>
  <div class="card"><span>Reject</span><b>{cs.get('reject', '—')}</b></div>
  <div class="card"><span>Review</span><b>{cs.get('review', '—')}</b></div>
  <div class="card"><span>Indexados</span><b>{cs.get('indexados', idx.get('indexados', '—'))}</b></div>
  <div class="card"><span>Chunks</span><b>{idx.get('chunks', tok.get('index_chunks', '—'))}</b></div>
  <div class="card highlight"><span>Tokens index</span><b>{escape(str(tok.get('index_tokens_fmt', '—')))}</b></div>
  <div class="card"><span>Paginas OCR</span><b>{ocr.get('staged_pages_processed', 0)}</b></div>
  <div class="card"><span>Planos scan</span><b>{ocr.get('planos_detected', 0)}</b></div>
</div>

<h2 style="margin-top:8px">Detalle por area</h2>
<p class="muted" style="margin:0 0 8px">Selecciona una tarjeta para ver tablas y datos completos.</p>
<div class="detail-cards" id="detail-cards">
  <div class="detail-card active" data-panel="panel-tokens">
    <div class="dc-title">Tokens e indice</div>
    <div class="dc-kpi">{escape(str(tok.get('index_tokens_fmt', '—')))}</div>
    <div class="dc-sub">{tok.get('index_chunks', 0):,} chunks · {tok.get('index_docs', '—')} docs</div>
  </div>
  <div class="detail-card" data-panel="panel-quality">
    <div class="dc-title">Calidad RAG</div>
    <div class="dc-kpi">{golden_mrr}</div>
    <div class="dc-sub">MRR golden · smoke {smoke_pass}/{smoke_total}</div>
  </div>
  <div class="detail-card" data-panel="panel-ocr">
    <div class="dc-title">OCR y planos</div>
    <div class="dc-kpi">{ocr.get('staged_documents', 0)}</div>
    <div class="dc-sub">{ocr.get('staged_pages_processed', 0)} pag procesadas · {ocr.get('planos_detected', 0)} planos</div>
  </div>
  <div class="detail-card" data-panel="panel-folders">
    <div class="dc-title">Cobertura carpetas</div>
    <div class="dc-kpi">{len(report.get('coverage_by_folder') or [])}</div>
    <div class="dc-sub">carpetas del corpus · {cs.get('indexados', idx.get('indexados', '—'))} indexados</div>
  </div>
  <div class="detail-card" data-panel="panel-phase0">
    <div class="dc-title">Fase 0</div>
    <div class="dc-kpi">{cs.get('pass', '—')}</div>
    <div class="dc-sub">pass · {cs.get('reject', '—')} reject · {len(report.get('phase0_by_extension') or {})} extensiones</div>
  </div>
  <div class="detail-card" data-panel="panel-rejects">
    <div class="dc-title">Rechazos</div>
    <div class="dc-kpi">{cs.get('reject', '—')}</div>
    <div class="dc-sub">{reject_count} motivos distintos registrados</div>
  </div>
  <div class="detail-card" data-panel="panel-topdocs">
    <div class="dc-title">Top documentos</div>
    <div class="dc-kpi">{len(report.get('index_top_docs') or [])}</div>
    <div class="dc-sub">mayor volumen de tokens indexados</div>
  </div>
  <div class="detail-card" data-panel="panel-jobs">
    <div class="dc-title">Jobs</div>
    <div class="dc-kpi">{registry.get('job_count', 0)}</div>
    <div class="dc-sub">registro ingestion-registry</div>
  </div>
  <div class="detail-card" data-panel="panel-docs">
    <div class="dc-title">Todos los documentos</div>
    <div class="dc-kpi">{report.get('document_count', 0)}</div>
    <div class="dc-sub">filtrable desde analysis-status</div>
  </div>
</div>

<div class="detail-panel active" id="panel-tokens">
  <h2>Tokens e indice</h2>
  <table><tbody>
    <tr><td>Documentos indexados</td><td>{tok.get('index_docs', '—')}</td></tr>
    <tr><td>Chunks</td><td>{int(tok.get('index_chunks') or 0):,}</td></tr>
    <tr><td>Tokens totales</td><td>{tok.get('index_tokens', 0):,}</td></tr>
    <tr><td>Promedio tok/chunk</td><td>{tok.get('avg_tokens_per_chunk', '—')}</td></tr>
    <tr><td>Revisiones IA</td><td>{tok.get('ai_reviews', 0)} ({tok.get('ai_total_tokens_fmt', 0)} tok)</td></tr>
    <tr><td>Progreso indice</td><td>{escape(str(tok.get('progress') or '—'))}</td></tr>
  </tbody></table>
</div>

<div class="detail-panel" id="panel-quality">
  <h2>Calidad recuperacion</h2>
  <table><tbody>
    <tr><td>Golden MRR</td><td>{golden_mrr}</td></tr>
    <tr><td>Golden recall@5</td><td>{golden_recall}</td></tr>
    <tr><td>Smoke test</td><td>{smoke_pass} / {smoke_total}</td></tr>
    <tr><td>Validacion RAG</td><td>{rag_ok} / {rag_total}</td></tr>
  </tbody></table>
</div>

<div class="detail-panel" id="panel-ocr">
  <h2>OCR y planos</h2>
  <table><tbody>
    <tr><td>Docs OCR staging</td><td>{ocr.get('staged_documents', 0)}</td></tr>
    <tr><td>Paginas OCR procesadas</td><td>{ocr.get('staged_pages_processed', 0)}</td></tr>
    <tr><td>Planos detectados (scan)</td><td>{ocr.get('planos_detected', 0)}</td></tr>
    <tr><td>Paginas OCR pend/proy.</td><td>{ocr.get('planos_pages_needs_ocr', 0)}</td></tr>
    <tr><td>Piloto OCR paginas</td><td>{ocr.get('pilot_pages', 0)}</td></tr>
  </tbody></table>
  <table><thead><tr><th>Doc OCR</th><th>Calidad</th><th>Pags</th><th>Conf.</th><th>Motor</th><th></th></tr></thead>
  <tbody>{ocr_rows or '<tr><td colspan="6">Sin staging OCR</td></tr>'}</tbody></table>
</div>

<div class="detail-panel" id="panel-folders">
  <h2>Cobertura por carpeta</h2>
  <table><thead><tr><th>Carpeta</th><th>Total</th><th>Pass</th><th>Reject</th><th>Index</th><th>%</th></tr></thead>
  <tbody>{folder_rows or '<tr><td colspan="6">Sin datos</td></tr>'}</tbody></table>
</div>

<div class="detail-panel" id="panel-phase0">
  <h2>Fase 0 por extension</h2>
  <table><thead><tr><th>Ext</th><th>Pass</th><th>Review</th><th>Reject</th><th>Excluido</th></tr></thead>
  <tbody>{ext_rows or '<tr><td colspan="5">Sin datos</td></tr>'}</tbody></table>
</div>

<div class="detail-panel" id="panel-rejects">
  <h2>Rechazos frecuentes</h2>
  <table><thead><tr><th>#</th><th>Motivo</th></tr></thead>
  <tbody>{reject_rows or '<tr><td colspan="2">Sin rejects</td></tr>'}</tbody></table>
</div>

<div class="detail-panel" id="panel-topdocs">
  <h2>Top documentos por tokens</h2>
  <table><thead><tr><th>Archivo</th><th>Estado</th><th>Chunks</th><th>Tokens</th></tr></thead>
  <tbody>{top_index or '<tr><td colspan="4">Sin index-corpus-summary</td></tr>'}</tbody></table>
</div>

<div class="detail-panel" id="panel-jobs">
  <h2>Registro de trabajos (ultimos)</h2>
  <table><thead><tr><th>Fecha</th><th>Tipo</th><th>Nota</th></tr></thead>
  <tbody>{job_rows or '<tr><td colspan="3">Sin jobs en ingestion-registry.json</td></tr>'}</tbody></table>
</div>

<div class="detail-panel" id="panel-docs">
  <h2>Detalle por documento <span class="muted">({report.get('document_count', 0)} filas)</span></h2>
<div class="doc-tools">
  <input id="doc-q" type="search" placeholder="Filtrar nombre, tipo, estado…" style="min-width:240px"/>
  <select id="doc-status"><option value="">Todos estados Fase 0</option>
    <option value="pass">pass</option><option value="reject">reject</option><option value="review">review</option>
    <option value="excluido">excluido</option></select>
  <select id="doc-index"><option value="">Indice: todos</option>
    <option value="active">indexado</option><option value="pendiente">pendiente</option>
    <option value="duplicado">duplicado</option><option value="error">error</option></select>
  <span class="muted" id="doc-count"></span>
</div>
<div class="doc-table-wrap">
  <table id="doc-table"><thead><tr>
    <th>Archivo</th><th>Ext</th><th>Tipo</th><th>Fase 0</th><th>Indice</th><th>Chunks</th><th>Notas</th><th></th>
  </tr></thead><tbody id="doc-body"><tr><td colspan="8" class="muted">Cargando analysis-status.json…</td></tr></tbody></table>
</div>
</div>

<div class="links">
  <strong>Fuentes:</strong>
  <a href="analysis-status.json">analysis-status.json</a>
  <a href="index-corpus-summary.json">index-corpus-summary.json</a>
  <a href="ingestion-registry.json">ingestion-registry.json</a>
  <a href="plan-scan.json">plan-scan.json</a>
  <a href="data-analysis/report.json">data-analysis/report.json</a>
  <a href="data-quality.html">data-quality.html</a>
  <a href="review.html">revision hub</a>
</div>

<script>
(function() {{
  document.querySelectorAll('.detail-card').forEach(card => {{
    card.addEventListener('click', () => {{
      const panelId = card.dataset.panel;
      document.querySelectorAll('.detail-card').forEach(c => c.classList.remove('active'));
      document.querySelectorAll('.detail-panel').forEach(p => p.classList.remove('active'));
      card.classList.add('active');
      const panel = document.getElementById(panelId);
      if (panel) {{
        panel.classList.add('active');
        panel.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
      }}
    }});
  }});

  const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
  let rows = [];

  async function loadDocs() {{
    try {{
      const res = await fetch('analysis-status.json');
      const data = await res.json();
      rows = data.analyses || [];
      renderDocs();
    }} catch (e) {{
      document.getElementById('doc-body').innerHTML = '<tr><td colspan="8">Error cargando analysis-status.json</td></tr>';
    }}
  }}

  function renderDocs() {{
    const q = (document.getElementById('doc-q').value || '').toLowerCase();
    const st = document.getElementById('doc-status').value;
    const ix = document.getElementById('doc-index').value;
    const filtered = rows.filter(r => {{
      if (st && r.status !== st) return false;
      if (ix && (r.index_status || 'pendiente') !== ix) return false;
      if (!q) return true;
      const blob = [r.name, r.tipo, r.status, r.index_status, r.relative_path, ...(r.notes||[])].join(' ').toLowerCase();
      return blob.includes(q);
    }}).slice(0, 500);
    document.getElementById('doc-count').textContent = filtered.length + ' / ' + rows.length + ' (max 500 visibles)';
    const body = filtered.map(r => {{
      const note = (r.notes && r.notes[0]) ? r.notes[0] : '';
      const link = r.review_url ? '<a href="' + esc(r.review_url) + '">Review</a>' : '';
      return '<tr><td>' + esc(r.name) + '</td><td>' + esc(r.extension) + '</td><td>' + esc(r.tipo) +
        '</td><td>' + esc(r.status) + '</td><td>' + esc(r.index_status || '—') + '</td><td>' +
        esc(r.index_chunks ?? '') + '</td><td class="muted">' + esc(note).slice(0,80) + '</td><td>' + link + '</td></tr>';
    }}).join('');
    document.getElementById('doc-body').innerHTML = body || '<tr><td colspan="8">Sin coincidencias</td></tr>';
  }}

  ['doc-q','doc-status','doc-index'].forEach(id => {{
    document.getElementById(id).addEventListener('input', renderDocs);
    document.getElementById(id).addEventListener('change', renderDocs);
  }});

  async function pollLive() {{
    try {{
      const res = await fetch('/api/ingestion-live');
      const s = await res.json();
      const sum = s.summary || {{}};
      const idx = s.index_summary || {{}};
      const p0 = s.phase0_activity || {{}};
      const ix = s.index_activity || {{}};
      document.getElementById('live-text').textContent =
        'Live · pass ' + (sum.pass ?? '—') + ' · index ' + (sum.indexados ?? '—') +
        ' · chunks ' + (idx.chunks ?? '—') +
        (p0.file ? ' · Fase0: ' + p0.file : '') +
        (ix.file ? ' · Index: ' + ix.file : '');
    }} catch (e) {{
      document.getElementById('live-text').textContent = 'Live no disponible (serve_local)';
    }}
  }}

  loadDocs();
  pollLive();
  setInterval(pollLive, 8000);
}})();
</script>
</body></html>"""


def write_ingestion_results(out_dir: Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    report = build_ingestion_results(out_dir)
    json_path = out_dir / "ingestion-results.json"
    html_path = out_dir / "ingestion-results.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_ingestion_results_html(report, out_dir=out_dir), encoding="utf-8")
    return json_path, html_path
