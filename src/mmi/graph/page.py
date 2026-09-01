"""UI Mapa de Conocimiento MMI (Fase E1)."""

from __future__ import annotations

from pathlib import Path


def render_mapa_html(out_dir: Path | None = None) -> str:
    from mmi.analysis.review_shell import render_review_nav, review_nav_css

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MMI — Mapa de Conocimiento</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
{review_nav_css()}
  :root {{
    --accent: #c4a8ff;
    --panel: #1a1824;
    --border: #3a3350;
  }}
  body {{ margin: 0; background: #121018; color: #ece8f4; font-family: Segoe UI, system-ui, sans-serif; }}
  .wrap {{ display: flex; flex-direction: column; height: 100vh; }}
  .topbar {{
    padding: 12px 16px; border-bottom: 1px solid var(--border); background: #18141f;
    display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  }}
  .topbar input[type=search] {{
    flex: 1; min-width: 220px; padding: 10px 12px; border-radius: 8px;
    border: 1px solid #444; background: #0f0d14; color: #eee;
  }}
  .topbar label {{ font-size: 0.82rem; color: #9a94aa; display: flex; align-items: center; gap: 6px; }}
  .topbar input[type=range] {{ width: 100px; }}
  button {{
    padding: 9px 14px; border-radius: 8px; border: 1px solid #444; background: #2a2438;
    color: #fff; cursor: pointer; font-weight: 600;
  }}
  button.primary {{ background: #5b3fd4; border-color: #5b3fd4; }}
  button:disabled {{ opacity: 0.5; cursor: wait; }}
  .main {{ flex: 1; display: grid; grid-template-columns: 220px 1fr 320px; min-height: 0; }}
  .filters, .detail {{
    border-right: 1px solid var(--border); background: var(--panel); overflow: auto; padding: 12px;
  }}
  .detail {{ border-right: none; border-left: 1px solid var(--border); }}
  .filters h2, .detail h2 {{ margin: 0 0 10px; font-size: 0.85rem; color: var(--accent); text-transform: uppercase; letter-spacing: 0.04em; }}
  .filters label {{ display: block; font-size: 0.78rem; color: #9a94aa; margin: 10px 0 4px; }}
  .filters input, .filters select {{
    width: 100%; box-sizing: border-box; padding: 7px 8px; border-radius: 6px;
    border: 1px solid #3a3350; background: #0f0d14; color: #eee;
  }}
  .view-tabs {{ display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }}
  .view-tabs button {{ font-size: 0.78rem; padding: 6px 10px; }}
  .view-tabs button.active {{ background: #5b3fd4; border-color: #5b3fd4; }}
  #graph {{ background: radial-gradient(circle at 30% 20%, #1f1a2e, #0e0c12); min-height: 0; }}
  #status {{ font-size: 0.82rem; color: #9a94aa; padding: 6px 16px; border-top: 1px solid var(--border); }}
  .meta {{ font-size: 0.82rem; color: #b0a8c0; line-height: 1.5; }}
  .meta b {{ color: #e8e0f8; }}
  .preview {{
    margin-top: 10px; padding: 10px; border-radius: 8px; background: #0f0d14;
    border: 1px solid #2a2438; font-size: 0.82rem; line-height: 1.45; max-height: 200px; overflow: auto;
  }}
  .ask-box {{ margin-top: 12px; }}
  .ask-box input {{ width: 100%; box-sizing: border-box; margin-bottom: 8px; padding: 8px; border-radius: 6px; border: 1px solid #3a3350; background: #0f0d14; color: #eee; }}
  .answer {{ margin-top: 10px; font-size: 0.85rem; line-height: 1.5; white-space: pre-wrap; }}
  .refs {{ margin-top: 8px; font-size: 0.78rem; color: #9a94aa; }}
  .refs li {{ margin-bottom: 4px; }}
  .banner {{ margin-top: 8px; padding: 8px 10px; border-radius: 6px; background: #3a2020; border: 1px solid #6a3030; color: #f0b0b0; font-size: 0.8rem; }}
  .motor-link {{ display: inline-block; margin-top: 10px; color: #8ab4ff; font-size: 0.82rem; }}
  .sel-count {{ font-size: 0.78rem; color: #9a94aa; margin-top: 6px; }}
  @media (max-width: 960px) {{
    .main {{ grid-template-columns: 1fr; grid-template-rows: auto 1fr auto; }}
    .filters {{ border-right: none; border-bottom: 1px solid var(--border); }}
    .detail {{ border-left: none; border-top: 1px solid var(--border); }}
  }}
</style>
</head>
<body>
<div class="wrap">
  {render_review_nav("mapa")}
  <div class="topbar">
    <input id="query" type="search" placeholder="Búsqueda semántica — ej. FMECA enfriamiento" />
    <button class="primary" id="btnSearch">Explorar</button>
    <label>Similitud ≥ <span id="simVal">0.72</span>
      <input id="simRange" type="range" min="0.5" max="0.95" step="0.01" value="0.72"/>
    </label>
    <button id="btnExpand" disabled>Expandir relaciones</button>
  </div>
  <div class="main">
    <aside class="filters">
      <h2>Filtros</h2>
      <label>Activo / tag</label>
      <input id="fAsset" placeholder="STG-01"/>
      <label>Área (dominio)</label>
      <select id="fDominio"><option value="">—</option></select>
      <label>Tipo documento</label>
      <select id="fTipo"><option value="">—</option></select>
      <label>Falla / síntoma</label>
      <input id="fFailure" placeholder="vibración, temperatura"/>
      <label>Documento (clave)</label>
      <input id="fDocKey" placeholder="FMECA, GUIGS"/>
      <label>Versión / vigencia</label>
      <select id="fVersion"><option value="">—</option></select>
      <button type="button" id="btnApplyFilters" style="width:100%;margin-top:12px">Aplicar filtros</button>
      <div class="view-tabs" style="margin-top:14px">
        <button type="button" class="view-btn active" data-view="global">Global</button>
        <button type="button" class="view-btn" data-view="documents">Docs</button>
        <button type="button" class="view-btn" data-view="concepts">Conceptos</button>
      </div>
    </aside>
    <div id="graph"></div>
    <aside class="detail">
      <h2>Selección</h2>
      <div id="detail" class="meta">Selecciona un nodo en el grafo.</div>
      <div id="selCount" class="sel-count"></div>
      <a id="motorLink" class="motor-link" href="#" style="display:none">Abrir en Motor MMI →</a>
      <div class="ask-box">
        <input id="askQ" placeholder="Preguntar sobre nodos seleccionados"/>
        <button id="btnAsk" disabled>Preguntar</button>
        <div id="askAnswer" class="answer"></div>
      </div>
    </aside>
  </div>
  <div id="status">Listo.</div>
</div>
<script>
const state = {{
  view: 'global',
  minSimilarity: 0.72,
  graph: null,
  network: null,
  selected: new Set(),
  lastPayload: null,
}};

const kindColor = {{
  chunk: '#8ab4ff',
  document: '#c4a8ff',
  asset: '#8fddb0',
  concept: '#f0d080',
}};

function filters() {{
  return {{
    asset: document.getElementById('fAsset').value.trim(),
    dominio: document.getElementById('fDominio').value,
    tipo: document.getElementById('fTipo').value,
    failure: document.getElementById('fFailure').value.trim(),
    document_key: document.getElementById('fDocKey').value.trim(),
    version_label: document.getElementById('fVersion').value,
  }};
}}

function updateSelectionUi(payload) {{
  const n = state.selected.size;
  document.getElementById('selCount').textContent = n ? `${{n}} nodo(s) seleccionado(s)` : '';
  document.getElementById('btnExpand').disabled = n === 0;
  document.getElementById('btnAsk').disabled = n === 0;
  const motor = document.getElementById('motorLink');
  let asset = '';
  if (payload && n) {{
    for (const id of state.selected) {{
      const node = payload.nodes.find(x => x.id === id);
      if (!node) continue;
      if (node.kind === 'asset') {{ asset = node.label; break; }}
      if ((node.asset_codes || []).length) {{ asset = node.asset_codes[0]; break; }}
    }}
  }}
  if (asset) {{
    motor.href = 'motor.html?asset=' + encodeURIComponent(asset);
    motor.style.display = 'inline-block';
  }} else {{
    motor.style.display = 'none';
  }}
}}

function setStatus(msg, ok) {{
  const el = document.getElementById('status');
  el.textContent = msg;
  el.style.color = ok ? '#8fddb0' : '#9a94aa';
}}

async function api(path, body) {{
  const res = await fetch(path, {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(body),
  }});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}}

function renderGraph(payload) {{
  state.lastPayload = payload;
  const nodes = new vis.DataSet(payload.nodes.map(n => ({{
    id: n.id,
    label: n.label.length > 36 ? n.label.slice(0, 34) + '…' : n.label,
    title: n.citation || n.label,
    color: kindColor[n.kind] || '#aaa',
    font: {{ color: '#f0eef8', size: 12 }},
    borderWidth: state.selected.has(n.id) ? 3 : 1,
    borderWidthSelected: 3,
  }})));
  const edges = new vis.DataSet(payload.edges.map(e => ({{
    id: e.id,
    from: e.source,
    to: e.target,
    width: Math.max(1, e.weight * 2),
    color: {{ color: e.kind === 'similar_to' ? '#6a5acd' : '#444', opacity: 0.7 }},
    title: e.kind + ' (' + e.weight + ')',
  }})));
  const container = document.getElementById('graph');
  const data = {{ nodes, edges }};
  const options = {{
    physics: {{ stabilization: {{ iterations: 120 }}, barnesHut: {{ gravitationalConstant: -8000 }} }},
    interaction: {{ hover: true, multiselect: true }},
  }};
  if (state.network) state.network.destroy();
  state.network = new vis.Network(container, data, options);
  state.network.on('click', params => {{
    if (!params.nodes.length) return;
    const id = params.nodes[0];
    if (params.event.srcEvent.shiftKey) {{
      if (state.selected.has(id)) state.selected.delete(id);
      else state.selected.add(id);
    }} else {{
      state.selected.clear();
      state.selected.add(id);
    }}
    document.getElementById('btnExpand').disabled = state.selected.size === 0;
    document.getElementById('btnAsk').disabled = state.selected.size === 0;
    showNode(id, payload.nodes.find(n => n.id === id));
    updateSelectionUi(payload);
    renderGraph(payload);
  }});
}}

async function showNode(id, cached) {{
  const el = document.getElementById('detail');
  if (!cached) {{
    try {{
      const res = await fetch('/api/graph/node/' + encodeURIComponent(id));
      cached = await res.json();
    }} catch (e) {{
      el.textContent = 'No se pudo cargar el nodo.';
      return;
    }}
  }}
  el.innerHTML = `
    <div><b>${{cached.label}}</b></div>
    <div>Tipo: ${{cached.kind}} · score ${{Number(cached.score || 0).toFixed(3)}}</div>
    <div>${{cached.tipo || ''}} ${{cached.dominio ? '· ' + cached.dominio : ''}}</div>
    <div>${{cached.citation || cached.document_key || ''}}</div>
    <div class="preview">${{(cached.content_preview || '').replace(/</g,'&lt;')}}</div>
  `;
}}

async function runSearch() {{
  const query = document.getElementById('query').value.trim();
  if (!query) return;
  setStatus('Buscando…');
  try {{
    const data = await api('/api/graph/search', {{
      query, limit: 10, min_similarity: state.minSimilarity, view: state.view, filters: filters(),
    }});
    state.selected.clear();
    updateSelectionUi(data);
    renderGraph(data);
    setStatus(`${{data.count.nodes}} nodos · ${{data.count.edges}} aristas · ${{data.elapsed_ms}} ms`, true);
    history.replaceState(null, '', 'mapa.html?q=' + encodeURIComponent(query));
  }} catch (e) {{
    setStatus('Error: ' + e.message);
  }}
}}

async function runExpand() {{
  if (!state.selected.size) return;
  setStatus('Expandiendo…');
  try {{
    const data = await api('/api/graph/expand', {{
      node_ids: Array.from(state.selected),
      limit: 12,
      min_similarity: state.minSimilarity,
      view: state.view,
      filters: filters(),
      graph: state.lastPayload,
    }});
    renderGraph(data);
    setStatus(`Expandido: ${{data.count.nodes}} nodos · ${{data.count.edges}} aristas`, true);
  }} catch (e) {{
    setStatus('Error: ' + e.message);
  }}
}}

async function runAsk() {{
  const q = document.getElementById('askQ').value.trim() || document.getElementById('query').value.trim();
  if (!q || !state.selected.size) return;
  const el = document.getElementById('askAnswer');
  el.textContent = 'Generando…';
  try {{
    const data = await api('/api/graph/ask', {{
      query: q,
      node_ids: Array.from(state.selected),
      limit: 8,
    }});
    let html = '<div class="answer">' + (data.answer || '(sin respuesta)').replace(/</g,'&lt;') + '</div>';
    if (data.conflict_banner && data.conflict_banner.visible) {{
      html += '<div class="banner">' + (data.conflict_banner.message || 'Posible conflicto entre versiones') + '</div>';
    }}
    if ((data.references || []).length) {{
      html += '<ul class="refs">' + data.references.map(r =>
        '<li>[' + r.index + '] ' + (r.citation || r.titulo || '') + '</li>'
      ).join('') + '</ul>';
    }}
    el.innerHTML = html;
  }} catch (e) {{
    el.textContent = 'Error: ' + e.message;
  }}
}}

async function loadFilters() {{
  try {{
    const data = await fetch('/api/graph/filters').then(r => r.json());
    const dom = document.getElementById('fDominio');
    const tipo = document.getElementById('fTipo');
    const ver = document.getElementById('fVersion');
    (data.dominios || []).forEach(v => {{
      const o = document.createElement('option'); o.value = v; o.textContent = v; dom.appendChild(o);
    }});
    (data.tipos || []).forEach(v => {{
      const o = document.createElement('option'); o.value = v; o.textContent = v; tipo.appendChild(o);
    }});
    (data.version_labels || []).forEach(v => {{
      const o = document.createElement('option'); o.value = v; o.textContent = v; ver.appendChild(o);
    }});
  }} catch (_) {{}}
}}

document.getElementById('btnApplyFilters').onclick = () => {{
  if (document.getElementById('query').value.trim()) runSearch();
}};
document.getElementById('btnSearch').onclick = runSearch;
document.getElementById('btnExpand').onclick = runExpand;
document.getElementById('btnAsk').onclick = runAsk;
document.getElementById('query').addEventListener('keydown', e => {{ if (e.key === 'Enter') runSearch(); }});
document.getElementById('simRange').oninput = e => {{
  state.minSimilarity = Number(e.target.value);
  document.getElementById('simVal').textContent = state.minSimilarity.toFixed(2);
}};
document.querySelectorAll('.view-btn').forEach(btn => {{
  btn.onclick = () => {{
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.view = btn.dataset.view;
    if (document.getElementById('query').value.trim()) runSearch();
  }};
}});

loadFilters();
const params = new URLSearchParams(location.search);
if (params.get('q')) {{
  document.getElementById('query').value = params.get('q');
  runSearch();
}}
</script>
</body>
</html>"""
