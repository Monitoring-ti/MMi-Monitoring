"""Pantalla Motor MMI — consulta por activo + síntoma (M1 fixture)."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

_DEFAULT_FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "motor-demo.json"


def load_motor_fixture(path: Path | None = None) -> dict:
    fixture_path = path or _DEFAULT_FIXTURE
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def render_motor_html(out_dir: Path | None = None, *, fixture: dict | None = None) -> str:
    from mmi.analysis.review_shell import render_review_nav, review_nav_css
    from mmi.motor.discrepancies import process_discrepancies
    from mmi.motor.eam_history import build_eam_history_payload

    data = fixture or load_motor_fixture()
    assets = data.get("assets") or []
    demo = dict(data.get("demo_analysis") or {})
    if demo.get("asset_id"):
        aid = demo["asset_id"]
        symptom = demo.get("symptom") or ""
        demo["eam_history"] = build_eam_history_payload(aid, symptom)
        disc, banner = process_discrepancies(
            demo.get("discrepancies") or [],
            asset_id=aid,
            symptom=symptom,
            facts=demo.get("verified_facts") or [],
            hits=[],
        )
        demo["discrepancies"] = disc
        demo["discrepancy_banner"] = banner

    asset_options = "".join(
        f'<option value="{escape(a.get("id", ""))}">{escape(a.get("name", a.get("id", "")))}</option>'
        for a in assets
    )
    fixture_json = json.dumps(demo, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MMI — Motor MMI</title>
<style>
  :root {{
    font-family: Segoe UI, system-ui, sans-serif;
    color: #e8e8e8;
    background: #141414;
    --accent: #e6b84d;
    --accent-dim: #3d321a;
    --ok: #8fddb0;
    --warn: #e6c07b;
    --panel: #1e1e1e;
    --border: #333;
  }}
  body {{ margin: 0; padding: 20px 24px 48px; max-width: 1200px; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 6px; }}
  .meta {{ color: #9a9a9a; margin-bottom: 16px; font-size: 0.88rem; line-height: 1.5; }}
  .meta a {{ color: #8ab4ff; }}
  .badge-fixture {{
    display: inline-block; font-size: 0.72rem; padding: 3px 8px; border-radius: 999px;
    background: var(--accent-dim); color: var(--accent); margin-left: 8px; vertical-align: middle;
  }}
  .query-bar {{
    display: grid; grid-template-columns: 1fr auto auto auto; gap: 10px; align-items: end;
    padding: 16px; border-radius: 12px; background: var(--panel); border: 1px solid var(--border);
    margin-bottom: 16px;
  }}
  @media (max-width: 800px) {{ .query-bar {{ grid-template-columns: 1fr; }} }}
  label {{ display: block; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em;
    color: #8ab4ff; margin-bottom: 6px; }}
  input[type=text], select {{
    width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid #444;
    background: #111; color: #eee; font-size: 0.95rem; box-sizing: border-box;
  }}
  button {{
    padding: 11px 18px; border-radius: 8px; border: none; background: var(--accent);
    color: #1a1a1a; font-weight: 700; cursor: pointer; white-space: nowrap;
  }}
  button:hover {{ filter: brightness(1.06); }}
  button:disabled {{ opacity: 0.5; cursor: wait; }}
  #status {{ min-height: 1.2em; color: #9a9a9a; font-size: 0.86rem; margin-bottom: 12px; }}
  #status.ok {{ color: var(--ok); }}
  #status.err {{ color: #f85149; }}
  .empty-state {{
    padding: 48px 24px; text-align: center; color: #7a7a7a; border: 1px dashed #444;
    border-radius: 12px; background: #181818;
  }}
  .analysis {{ display: none; }}
  .analysis.visible {{ display: block; }}
  .analysis-grid {{
    display: grid; grid-template-columns: 1.2fr 1fr; gap: 14px; margin-bottom: 14px;
  }}
  @media (max-width: 900px) {{ .analysis-grid {{ grid-template-columns: 1fr; }} }}
  .panel {{
    border-radius: 12px; border: 1px solid var(--border); background: var(--panel); overflow: hidden;
  }}
  .panel-head {{
    padding: 10px 14px; font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.04em; border-bottom: 1px solid var(--border); color: #b0b0b0;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .panel-head .conf {{ color: var(--ok); font-size: 0.85rem; }}
  .panel-body {{ padding: 14px 16px; line-height: 1.55; font-size: 0.92rem; }}
  .diag-panel .panel-head {{ color: var(--accent); background: #1a1810; border-color: #4a3d1a; }}
  .fact-list, .hyp-list, .check-list, .disc-list, .src-list {{
    margin: 0; padding: 0; list-style: none;
  }}
  .fact-list li, .hyp-list li {{
    padding: 10px 0; border-bottom: 1px solid #2a2a2a;
  }}
  .fact-list li:last-child, .hyp-list li:last-child {{ border-bottom: none; }}
  .fact-src {{ display: block; font-size: 0.78rem; color: #8a9ab0; margin-top: 4px; }}
  .fact-measure {{
    display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; font-size: 0.8rem;
  }}
  .fact-pill {{
    padding: 3px 8px; border-radius: 6px; background: #252525; border: 1px solid #3a3a3a;
  }}
  .fact-pill.warn {{ border-color: #8a5020; color: var(--warn); background: #2a2018; }}
  .fact-pill.ok {{ border-color: #2a5a3a; color: var(--ok); }}
  .fact-conf {{ font-size: 0.72rem; color: #7a9a7a; margin-left: 6px; }}
  .hyp-score {{
    float: right; font-weight: 700; color: var(--accent); font-size: 0.9rem;
  }}
  .hyp-note {{
    font-size: 0.78rem; color: var(--warn); margin: 8px 0 12px; padding: 8px 10px;
    background: #2a2418; border-radius: 6px; border: 1px solid #4a3d20;
  }}
  .hyp-facts {{
    display: block; margin-top: 4px; font-size: 0.76rem; color: #7a8a9a;
  }}
  .hyp-facts span {{
    display: inline-block; margin-right: 6px; padding: 1px 6px; border-radius: 4px;
    background: #222; border: 1px solid #333;
  }}
  .check-list li {{
    padding: 8px 0 8px 28px; position: relative; border-bottom: 1px solid #2a2a2a;
    cursor: pointer; user-select: none;
  }}
  .check-list li::before {{
    content: "☐"; position: absolute; left: 4px; color: #8ab4ff;
  }}
  .check-list li.checked::before {{ content: "☑"; color: var(--ok); }}
  .check-list li.urgent::before {{ color: #f85149; }}
  .check-priority {{
    font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em;
    color: #9a9a9a; margin-right: 6px;
  }}
  .check-list li.urgent .check-priority {{ color: #f85149; }}
  .disc-banner {{
    display: none; margin-bottom: 14px; padding: 12px 16px; border-radius: 10px;
    background: #2a2018; border: 1px solid #8a5020; color: var(--warn); font-size: 0.9rem;
  }}
  .disc-banner.visible {{ display: block; }}
  .disc-list li {{
    padding: 8px 12px; margin-bottom: 8px; border-radius: 8px;
    background: #2a2018; border: 1px solid #5a4020; color: var(--warn); font-size: 0.88rem;
  }}
  .disc-rule {{ font-size: 0.7rem; color: #9a8a7a; margin-right: 6px; text-transform: uppercase; }}
  .eam-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  .eam-table th, .eam-table td {{ padding: 8px 10px; border-bottom: 1px solid #2a2a2a; text-align: left; }}
  .eam-table th {{ color: #8ab4ff; font-size: 0.72rem; text-transform: uppercase; }}
  .eam-mtbf-warn {{ color: #f85149; }}
  .src-list li {{ padding: 6px 0; color: #8ab4ff; font-size: 0.86rem; }}
  .export-row {{ margin-top: 14px; text-align: right; display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }}
  .export-row button {{ background: #2a2a2a; color: #ccc; border: 1px solid #444; font-weight: 500; }}
  .export-row button.primary {{ background: var(--accent); color: #1a1a1a; border: none; }}
  .print-footer {{
    display: none; margin-top: 24px; padding-top: 12px; border-top: 1px solid #444;
    font-size: 0.75rem; color: #9a9a9a;
  }}
  @media print {{
    body {{ background: #fff; color: #111; padding: 12px; max-width: none; }}
    .query-bar, #status, #empty-state, #api-warn, .export-row, nav, .badge-fixture {{ display: none !important; }}
    .analysis {{ display: block !important; }}
    .panel {{ border-color: #ccc; background: #fff; break-inside: avoid; }}
    .panel-head {{ color: #333; background: #f5f5f5; }}
    .hyp-note {{ color: #663; background: #fff8e6; border-color: #cc9; }}
    .check-list li {{ color: #111; }}
    .print-footer {{ display: block !important; color: #444; }}
  }}
  {review_nav_css()}
</style>
</head>
<body>
{render_review_nav("motor")}
<h1>Consultar motor MMI <span class="badge-fixture">M6 · discrepancias</span></h1>
<p class="meta">
  Análisis por <strong>activo + síntoma</strong> con hechos verificados, hipótesis rankeadas y checklist de verificación física.
  Conectado a <code>POST /api/motor/analyze</code> (corpus ODS1 + OpenRouter).
  · <a href="rag.html">Consulta RAG</a>
</p>

<div id="api-warn" class="meta" style="display:none;color:#e6c07b;margin-bottom:12px;padding:10px 14px;background:#2a2418;border:1px solid #4a3d20;border-radius:8px;">
  API motor no detectada. Reinicia el servidor:
  <code>python -m mmi.tools.serve_local --port 8773</code>
  (el proceso en 8773 puede ser una versión antigua sin <code>/api/motor/analyze</code>).
</div>

<form class="query-bar" id="motor-form" onsubmit="return false;">
  <div style="grid-column: 1 / -1;">
    <label for="symptom">Síntoma</label>
    <input type="text" id="symptom" name="symptom" placeholder="Ej. alta temperatura y caída de caudal en circuito de enfriamiento" autocomplete="off"/>
  </div>
  <div>
    <label for="asset">Activo</label>
    <select id="asset" name="asset">{asset_options}</select>
  </div>
  <div>
    <label for="window">Vigencia</label>
    <select id="window" name="window">
      <option value="24h">Últimas 24 h</option>
      <option value="7d">7 días</option>
      <option value="30d">30 días</option>
      <option value="custom">Personalizado</option>
    </select>
  </div>
  <div>
    <label>&nbsp;</label>
    <button type="button" id="analyze-btn">Analizar</button>
  </div>
</form>

<div id="status"></div>

<div class="empty-state" id="empty-state">
  Ingresa un síntoma y pulsa <strong>Analizar</strong> para ver el layout de diagnóstico (datos fixture M1).
</div>

<div class="analysis" id="analysis">
  <div class="disc-banner" id="disc-banner"></div>
  <div class="analysis-grid">
    <div class="panel diag-panel">
      <div class="panel-head">Diagnóstico del síntoma</div>
      <div class="panel-body" id="diagnosis-body"></div>
    </div>
    <div class="panel">
      <div class="panel-head">Evidencia soportada <span class="conf" id="conf-badge"></span></div>
      <div class="panel-body">
        <ul class="fact-list" id="facts-list"></ul>
      </div>
    </div>
  </div>

  <div class="panel" style="margin-bottom:14px;">
    <div class="panel-head">Hipótesis del sistema</div>
    <div class="panel-body">
      <p class="hyp-note">Inferencia IA — requiere criterio del especialista. No sustituye verificación en terreno.</p>
      <ul class="hyp-list" id="hyp-list"></ul>
    </div>
  </div>

  <div class="analysis-grid">
    <div class="panel">
      <div class="panel-head">Verificación física</div>
      <div class="panel-body">
        <ul class="check-list" id="check-list"></ul>
        <div class="export-row">
          <button type="button" id="copy-checks-btn">Copiar checklist</button>
          <button type="button" id="export-pdf-btn" class="primary">Exportar PDF</button>
        </div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head">Fuentes y evidencia</div>
      <div class="panel-body">
        <ul class="src-list" id="src-list"></ul>
      </div>
    </div>
  </div>

  <div class="panel" style="margin-top:14px;">
    <div class="panel-head">Histórico EAM</div>
    <div class="panel-body" id="eam-body">
      <p style="color:#7a7a7a;margin:0">Sin órdenes de trabajo en fixture.</p>
    </div>
  </div>

  <div class="panel" style="margin-top:14px;">
    <div class="panel-head">Discrepancias detectadas</div>
    <div class="panel-body">
      <ul class="disc-list" id="disc-list"></ul>
    </div>
  </div>

  <div class="print-footer" id="print-footer"></div>
</div>

<script>
const DEMO = {fixture_json};

function apiError(res, bodyText) {{
  if (res.status === 404) {{
    return 'API motor no disponible (404). Reinicia: python -m mmi.tools.serve_local --port 8773';
  }}
  if (bodyText && bodyText.trim().startsWith('<')) {{
    return 'El servidor devolvió HTML en lugar de JSON (proceso antiguo en :8773). Reinicia serve_local.';
  }}
  return 'HTTP ' + res.status;
}}

async function parseJsonResponse(res) {{
  const text = await res.text();
  try {{
    return JSON.parse(text);
  }} catch {{
    throw new Error(apiError(res, text));
  }}
}}

function esc(s) {{
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}}

async function checkMotorApi() {{
  if (location.protocol === 'file:') {{
    document.getElementById('api-warn').style.display = 'block';
    return;
  }}
  try {{
    const res = await fetch('/api/motor/health');
    const data = await parseJsonResponse(res);
    if (!data.ok || !data.motor_api) throw new Error('health');
  }} catch {{
    document.getElementById('api-warn').style.display = 'block';
  }}
}}

function setStatus(msg, cls) {{
  const el = document.getElementById('status');
  el.textContent = msg || '';
  el.className = cls || '';
}}

function renderAnalysis(data) {{
  const d = data.diagnosis || {{}};
  document.getElementById('diagnosis-body').innerHTML =
    '<p>' + esc(d.summary || '') + '</p>';
  document.getElementById('conf-badge').textContent =
    'Confianza ' + (d.confidence_label || '') + ' · ' + (d.confidence_pct || '—') + '%' +
    (d.verified_fact_count ? ' · ' + d.verified_fact_count + ' hechos' : '') +
    (d.document_backed_count ? ' · ' + d.document_backed_count + ' con doc' : '');

  function renderFact(f) {{
    let html = '<li><strong>[' + (f.citation_index || '—') + ']</strong> ' + esc(f.text);
    if (f.sensor) {{
      const lim = f.limit || {{}};
      const exceeded = lim.exceeded === true;
      const pills = '<span class="fact-pill">' + esc(f.sensor.tag) + ': ' +
        esc(String(f.sensor.value)) + ' ' + esc(f.sensor.unit) + '</span>';
      let limitPill = '';
      if (lim.value != null) {{
        limitPill = '<span class="fact-pill ' + (exceeded ? 'warn' : 'ok') + '">' +
          esc((lim.kind || 'límite') + ' ' + lim.value + ' ' + (lim.unit || '')) +
          (exceeded ? ' · excedido' : '') + '</span>';
      }}
      html += '<div class="fact-measure">' + pills + limitPill + '</div>';
    }}
    if (f.confidence && f.confidence.pct) {{
      html += '<span class="fact-conf">conf. ' + f.confidence.pct + '%</span>';
    }}
    html += '<span class="fact-src">' + esc((f.source && f.source.citation) || '') + '</span></li>';
    return html;
  }}

  document.getElementById('facts-list').innerHTML = (data.verified_facts || []).map(renderFact).join('');

  function renderHypothesis(h) {{
    const facts = (h.supported_facts || []).map(sf =>
      '<span>[' + sf.index + '] ' + esc(sf.tag || sf.text || '') + '</span>'
    ).join('');
    return '<li><span class="hyp-score">' + (h.confidence_pct || '—') + '%</span>' +
      '<strong>' + esc(h.id) + '</strong> — ' + esc(h.title) +
      '<br><small style="color:#9a9a9a">' + esc(h.rationale) + '</small>' +
      (facts ? '<span class="hyp-facts">Hechos: ' + facts + '</span>' : '') +
      '</li>';
  }}

  document.getElementById('hyp-list').innerHTML = (data.hypotheses || []).map(renderHypothesis).join('');

  function renderCheck(c, idx) {{
    const pri = c.priority === 'urgent' ? 'urgent' : 'normal';
  const label = c.priority === 'urgent' ? 'urgente' : 'rutina';
    return '<li class="' + pri + (c.checked ? ' checked' : '') + '" data-idx="' + idx + '">' +
      '<span class="check-priority">' + label + '</span>' + esc(c.text) + '</li>';
  }}

  const checks = data.physical_checks || [];
  const listEl = document.getElementById('check-list');
  listEl.innerHTML = checks.map(renderCheck).join('');
  listEl.querySelectorAll('li').forEach(li => {{
    li.addEventListener('click', () => {{
      const i = parseInt(li.dataset.idx, 10);
      checks[i].checked = !checks[i].checked;
      li.classList.toggle('checked', checks[i].checked);
    }});
  }});

  document.getElementById('src-list').innerHTML = (data.sources_preview || []).map(s =>
    '<li>' + esc(s) + '</li>'
  ).join('');

  const discs = data.discrepancies || [];
  document.getElementById('disc-list').innerHTML = discs.length
    ? discs.map(d => '<li><span class="disc-rule">' + esc(d.rule || d.kind || '') + '</span>' + esc(d.text) + '</li>').join('')
    : '<li style="color:#7a7a7a;border:none;background:transparent">Sin discrepancias detectadas</li>';

  const banner = data.discrepancy_banner || {{}};
  const bannerEl = document.getElementById('disc-banner');
  if (banner.visible) {{
    bannerEl.textContent = '⚠ ' + (banner.message || 'Discrepancia detectada');
    bannerEl.classList.add('visible');
  }} else {{
    bannerEl.classList.remove('visible');
    bannerEl.textContent = '';
  }}

  const eam = data.eam_history || {{}};
  const wos = eam.work_orders || [];
  const eamEl = document.getElementById('eam-body');
  if (!wos.length) {{
    eamEl.innerHTML = '<p style="color:#7a7a7a;margin:0">Sin órdenes de trabajo para este activo.</p>';
  }} else {{
    eamEl.innerHTML = '<table class="eam-table"><thead><tr><th>WO</th><th>Fecha</th><th>Causa</th><th>MTBF</th></tr></thead><tbody>' +
      wos.map(wo => {{
        const mtbf = wo.mtbf_hours != null ? wo.mtbf_hours + ' h' : '—';
        const exp = wo.mtbf_expected_hours;
        const warn = exp && wo.mtbf_hours < exp * 0.85;
        return '<tr><td>' + esc(wo.wo_code) + '</td><td>' + esc(wo.date) + '</td><td>' + esc(wo.cause) +
          '</td><td class="' + (warn ? 'eam-mtbf-warn' : '') + '">' + esc(mtbf) +
          (exp ? ' / ' + exp + ' h' : '') + '</td></tr>';
      }}).join('') + '</tbody></table>';
  }}

  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('analysis').classList.add('visible');

  const meta = data.export_meta || {{}};
  const footer = document.getElementById('print-footer');
  footer.innerHTML =
    '<strong>MMI Motor</strong> · Activo: ' + esc(meta.asset_id || data.asset?.id || '') +
    ' · Síntoma: ' + esc(data.symptom || '') +
    ' · ' + esc(meta.generated_at || new Date().toISOString()) +
    ' · Modelo: ' + esc(meta.model || data.model || '') +
    ' · motor_id: ' + esc(meta.motor_id || data.motor_id || '') +
    (meta.source_ids?.length ? ' · Fuentes: ' + esc(meta.source_ids.join(', ')) : '');

  window._motorPayload = data;
}}

async function runAnalyze() {{
  const symptom = document.getElementById('symptom').value.trim();
  const asset = document.getElementById('asset').value;
  const window = document.getElementById('window').value;
  if (!symptom) {{
    setStatus('Escribe un síntoma para analizar.', 'err');
    return;
  }}
  const btn = document.getElementById('analyze-btn');
  btn.disabled = true;
  setStatus('Analizando con corpus ODS1…', '');
  document.getElementById('analysis').classList.remove('visible');

  const u = new URL(location.href);
  u.searchParams.set('asset', asset);
  u.searchParams.set('q', symptom);
  u.searchParams.set('window', window);
  history.replaceState(null, '', u);

  try {{
    const res = await fetch('/api/motor/analyze', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ asset_id: asset, symptom: symptom, window: window, limit: 8 }}),
    }});
    const payload = await parseJsonResponse(res);
    if (!res.ok) throw new Error(payload.error || apiError(res));
    window._motorId = payload.motor_id;
    renderAnalysis(payload);
    setStatus(
      'Análisis · ' + (payload.evidence_count || 0) + ' evidencias · ' +
      (payload.elapsed_ms || '—') + ' ms · ' + (payload.model || ''),
      'ok'
    );
  }} catch (err) {{
    const payload = Object.assign({{}}, DEMO, {{ asset_id: asset, symptom: symptom, window: window }});
    renderAnalysis(payload);
    setStatus('API no disponible — fixture local: ' + err.message, 'err');
  }} finally {{
    btn.disabled = false;
  }}
}}

document.getElementById('analyze-btn').addEventListener('click', runAnalyze);

document.getElementById('copy-checks-btn').addEventListener('click', () => {{
  const checks = (window._motorPayload?.physical_checks || []);
  if (!checks.length) {{ setStatus('No hay checklist para copiar.', 'err'); return; }}
  const lines = checks.map(c =>
    (c.checked ? '[x] ' : '[ ] ') + (c.priority === 'urgent' ? '[URGENTE] ' : '') + c.text
  );
  const header = 'Checklist verificación física — ' + (window._motorPayload?.asset?.id || '') + '\\n';
  navigator.clipboard.writeText(header + lines.join('\\n')).then(() => {{
    setStatus('Checklist copiado al portapapeles.', 'ok');
  }}).catch(() => setStatus('No se pudo copiar.', 'err'));
}});

document.getElementById('export-pdf-btn').addEventListener('click', () => {{
  if (!window._motorPayload) {{ setStatus('Ejecuta un análisis primero.', 'err'); return; }}
  window.print();
}});

checkMotorApi();

(function initFromUrl() {{
  const p = new URLSearchParams(location.search);
  if (p.get('asset')) document.getElementById('asset').value = p.get('asset');
  if (p.get('window')) document.getElementById('window').value = p.get('window');
  if (p.get('q')) {{
    document.getElementById('symptom').value = p.get('q');
    runAnalyze();
  }}
}})();
</script>
</body>
</html>"""


def write_motor_html(out_dir: Path, *, fixture: dict | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "motor.html"
    path.write_text(render_motor_html(out_dir, fixture=fixture), encoding="utf-8")
    return path
