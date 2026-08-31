"""CLI y UI web de búsqueda híbrida MMI."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from mmi.search.engine import HybridSearchEngine, SearchResult


def _result_dict(r: SearchResult) -> dict:
    return {
        "point_id": r.point_id,
        "score": round(r.score, 4),
        "content": r.content,
        "document_id": r.document_id,
        "tipo": r.tipo,
        "dominio": r.dominio,
        "criticality_level": r.criticality_level,
        "section_path": r.section_path,
        "page_start": r.page_start,
        "page_end": r.page_end,
        "asset_codes": r.asset_codes,
        "titulo": r.titulo,
        "version_label": r.version_label,
        "citation": r.citation,
    }


def render_search_html() -> str:
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>MMI — Búsqueda con citas</title>
<style>
  :root { font-family: Segoe UI, system-ui, sans-serif; color: #e8e8e8; background: #1a1a1a; }
  body { margin: 0; padding: 24px; max-width: 960px; }
  h1 { font-size: 1.3rem; margin: 0 0 8px; }
  .meta { color: #9a9a9a; margin-bottom: 16px; font-size: 0.9rem; }
  .bar { display: flex; gap: 8px; margin-bottom: 16px; }
  input[type=search] { flex: 1; padding: 10px 12px; border-radius: 8px; border: 1px solid #444;
    background: #111; color: #eee; font-size: 1rem; }
  button { padding: 10px 16px; border-radius: 8px; border: none; background: #2a2a2a;
    color: #fff; font-weight: 600; cursor: pointer; border: 1px solid #444; }
  button.primary { background: #2b5cff; border-color: #2b5cff; }
  button:hover { filter: brightness(1.1); }
  .answer-box { border: 1px solid #2d4a2d; border-radius: 8px; padding: 16px; margin-bottom: 16px;
    background: #1a241a; line-height: 1.55; }
  .answer-box h2 { margin: 0 0 8px; font-size: 1rem; color: #8fddb0; }
  .answer-body h3 { margin: 14px 0 8px; font-size: 0.95rem; color: #b8e6c8; }
  .answer-body p { margin: 0 0 10px; color: #ddd; }
  .answer-body ul { margin: 0 0 10px; padding-left: 20px; color: #ddd; }
  .answer-body li { margin-bottom: 6px; }
  .refs-box { border: none; padding: 0; margin: 0; background: transparent; }
  details.optional-panel { border: 1px solid #2a3a5a; border-radius: 8px; padding: 10px 14px;
    margin-bottom: 14px; background: #1a1f2e; }
  details.optional-panel.evidence { border-color: #333; background: #1c1c1c; }
  details.optional-panel > summary { cursor: pointer; font-weight: 600; font-size: 0.92rem;
    color: #8ab4ff; list-style: none; }
  details.optional-panel.evidence > summary { color: #b0b0b0; }
  details.optional-panel > summary::-webkit-details-marker { display: none; }
  details.optional-panel[open] > summary { margin-bottom: 10px; }
  details.optional-panel .refs-list { margin-top: 4px; }
  .lazy-status { margin: 0; color: #8a8a8a; font-size: 0.84rem; font-style: italic; }
  .refs-list { margin: 0; padding-left: 0; list-style: none; }
  .refs-list li { margin-bottom: 10px; padding: 8px 10px; border-radius: 6px; background: #151a24;
    border: 1px solid #2a3344; font-size: 0.88rem; line-height: 1.4; }
  .refs-list li.cited { border-color: #3d5a8a; }
  .ref-num { display: inline-block; min-width: 2rem; font-weight: 700; color: #8ab4ff; }
  .ref-meta { color: #8a9ab0; font-size: 0.8rem; margin-top: 4px; }
  .ref-snippet { color: #9aa8bc; font-size: 0.82rem; margin-top: 6px; font-style: italic; }
  .cite-link { color: #8ab4ff; text-decoration: none; font-weight: 600; }
  .cite-link:hover { text-decoration: underline; }
  .hit.cited { border-color: #3d5a8a; }
  details.help { border: 1px solid #333; border-radius: 12px; padding: 14px 16px; margin-bottom: 16px;
    background: #1c1c1c; }
  details.help > summary { cursor: pointer; font-weight: 600; color: #d4e4ff; font-size: 1rem; }
  .help-intro { margin: 10px 0 12px; color: #9a9a9a; font-size: 0.86rem; line-height: 1.45; }
  .help-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(272px, 1fr)); gap: 12px; }
  .help-card { border: 1px solid #2f2f2f; border-radius: 10px; padding: 14px 14px 12px;
    background: linear-gradient(160deg, #222 0%, #1a1a1a 100%); transition: border-color .15s, box-shadow .15s; }
  .help-card:hover { border-color: #4a6288; box-shadow: 0 4px 14px rgba(0,0,0,.25); }
  .help-card-head { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; }
  .help-card-icon { width: 34px; height: 34px; border-radius: 8px; display: flex; align-items: center;
    justify-content: center; font-size: 0.72rem; font-weight: 700; flex-shrink: 0; background: #2a3344; color: #8ab4ff; }
  .help-card h3 { margin: 0; font-size: 0.9rem; color: #e8eef8; line-height: 1.3; }
  .help-card-tag { display: block; margin-top: 3px; font-size: 0.72rem; color: #7a8aa0; }
  .help-card ul { margin: 0 0 10px; padding-left: 16px; color: #aaa; font-size: 0.82rem; line-height: 1.45; }
  .help-card li { margin-bottom: 4px; }
  .help-card code { background: #111; padding: 1px 5px; border-radius: 4px; font-size: 0.78rem; }
  .help-card.wide { grid-column: 1 / -1; }
  .ex-btns { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
  .ex-btns button { background: #2a2a2a; border: 1px solid #444; font-weight: 400; font-size: 0.78rem;
    padding: 5px 9px; border-radius: 6px; color: #eee; cursor: pointer; }
  .ex-btns button:hover { filter: brightness(1.12); border-color: #5a7ab8; }
  .ex-btns button.search-only { border-color: #3a4a3a; color: #b8ddb0; }
  .hit { border: 1px solid #333; border-radius: 8px; padding: 14px; margin-bottom: 12px;
    background: #202020; }
  .hit h3 { margin: 0 0 6px; font-size: 0.95rem; color: #d4e4ff; }
  .badge { font-size: 0.72rem; padding: 2px 7px; border-radius: 999px; background: #2a2a2a;
    color: #aaa; margin-right: 6px; }
  .badge.seg { background: #3d321a; color: #e6c07b; }
  .cite { color: #8ab4ff; font-size: 0.85rem; margin-bottom: 8px; }
  .snippet { color: #ccc; font-size: 0.88rem; line-height: 1.45; white-space: pre-wrap; }
  #status { color: #9a9a9a; margin-top: 8px; }
  a { color: #8ab4ff; }
</style>
</head>
<body>
  <h1>Búsqueda híbrida — memoria técnica NCC30</h1>
  <p class="meta">Búsqueda: Qdrant + Supabase · Respuestas: <b>OpenRouter</b> (sin Gemini)</p>
  <div class="bar">
    <input id="q" type="search" placeholder="Pregunta concreta + términos del dominio (NCC-30, FMECA, GUIGS, checklist…)"/>
    <button id="go">Buscar</button>
    <button id="ask" class="primary">Responder con citas</button>
  </div>

  <details class="help">
    <summary>Cómo buscar mejor</summary>
    <p class="help-intro">Elige una tarjeta y haz clic en un ejemplo para cargar la consulta.</p>
    <div class="help-grid">

      <article class="help-card">
        <div class="help-card-head">
          <div class="help-card-icon">?</div>
          <div>
            <h3>Formular la pregunta</h3>
            <span class="help-card-tag">Preguntas completas</span>
          </div>
        </div>
        <ul>
          <li>Usa <b>preguntas completas</b>, no una sola palabra.</li>
          <li>Incluye <b>qué necesitas</b>: definición, criterio, paso, checklist.</li>
          <li>Añade <b>contexto</b>: fase, equipo o sección.</li>
        </ul>
        <div class="ex-btns">
          <button type="button" data-q="¿Cuáles son los criterios de criticidad según NCC-030?">Criterios criticidad</button>
          <button type="button" data-q="¿Qué es la mantenibilidad y cómo se evalúa según la guía Rev 6?">Definición mantenibilidad</button>
          <button type="button" data-q="¿Cuál es el alcance del análisis de mantenibilidad en proyectos de inversión?">Alcance M&amp;C</button>
        </div>
      </article>

      <article class="help-card">
        <div class="help-card-head">
          <div class="help-card-icon">DOC</div>
          <div>
            <h3>Documentos y códigos</h3>
            <span class="help-card-tag">GUIGS · NCC · PROGS</span>
          </div>
        </div>
        <ul>
          <li>Incluye el <b>código del documento</b>.</li>
          <li>Indica <b>revisión</b>: <code>Rev 6</code>, <code>Rev 02</code>.</li>
          <li>Combina norma + guía + procedimiento.</li>
        </ul>
        <div class="ex-btns">
          <button type="button" data-q="SGP-07MYC-GUIGS-00001 Rev 6 alcance mantenibilidad confiabilidad">GUIGS Rev 6</button>
          <button type="button" data-q="NCC-030 requisitos mantenibilidad confiabilidad proyectos">NCC-030</button>
          <button type="button" data-q="SGPD-07MYC-PROGS-0001 procedimiento estudios y proyectos">PROGS-0001</button>
          <button type="button" data-q="IFC 078 clasificación equipos criticidad">IFC 078</button>
        </div>
      </article>

      <article class="help-card">
        <div class="help-card-head">
          <div class="help-card-icon">✓</div>
          <div>
            <h3>Procedimientos y checklist</h3>
            <span class="help-card-tag">SOP · Anexo C</span>
          </div>
        </div>
        <ul>
          <li><b>Responder con citas</b> para pasos y flujos.</li>
          <li>Menciona <code>Anexo C</code> o <code>checklist</code>.</li>
          <li><b>Buscar</b> para texto crudo.</li>
        </ul>
        <div class="ex-btns">
          <button type="button" data-q="procedimiento mantenibilidad estudios y proyectos pasos etapas">Pasos SOP</button>
          <button type="button" data-q="Anexo C checklist accesibilidad cumplimiento mantenibilidad">Anexo C</button>
          <button type="button" data-q="aspectos análisis mantenibilidad confiabilidad checklist diseño">Checklist M&amp;C</button>
          <button type="button" class="search-only" data-action="search" data-q="checklist accesibilidad mantenimiento">Buscar</button>
        </div>
      </article>

      <article class="help-card">
        <div class="help-card-head">
          <div class="help-card-icon">⚙</div>
          <div>
            <h3>FMECA y RCM</h3>
            <span class="help-card-tag">Análisis de fallas</span>
          </div>
        </div>
        <ul>
          <li><code>FMECA</code> — modos de falla, efectos.</li>
          <li><code>RCM</code> — tareas recomendadas.</li>
          <li>Pregunta <b>cuándo aplicar</b> cada metodología.</li>
        </ul>
        <div class="ex-btns">
          <button type="button" data-q="modos de falla efectos criticidad FMECA análisis">FMECA</button>
          <button type="button" data-q="análisis RCM tareas de mantenimiento recomendadas">RCM</button>
          <button type="button" data-q="diferencia entre FMECA y RCM cuándo usar cada uno">FMECA vs RCM</button>
          <button type="button" data-q="FRMGS-0036 RCM plantilla análisis">FRMGS-0036</button>
        </div>
      </article>

      <article class="help-card">
        <div class="help-card-head">
          <div class="help-card-icon">!</div>
          <div>
            <h3>Seguridad y operación</h3>
            <span class="help-card-tag">LOTO · precauciones</span>
          </div>
        </div>
        <ul>
          <li>Prioriza fragmentos con <b>advertencias</b>.</li>
          <li>Usa <code>bloqueo</code>, <code>LOTO</code>, <code>antes de operar</code>.</li>
        </ul>
        <div class="ex-btns">
          <button type="button" data-q="advertencia seguridad bloqueo antes de operar equipo">Seguridad / LOTO</button>
          <button type="button" data-q="infraestructura crítica NCC30 definición">Infra. crítica</button>
          <button type="button" data-q="precauciones operación mantenimiento equipos">Precauciones</button>
        </div>
      </article>

      <article class="help-card">
        <div class="help-card-head">
          <div class="help-card-icon">⇄</div>
          <div>
            <h3>Buscar vs Responder</h3>
            <span class="help-card-tag">Modos de consulta</span>
          </div>
        </div>
        <ul>
          <li><b>Responder con citas</b> — definiciones, procedimientos, [1][2].</li>
          <li><b>Buscar</b> — solo fragmentos, sin redactar.</li>
          <li>Explora con Buscar, luego refina con citas.</li>
        </ul>
      </article>

      <article class="help-card">
        <div class="help-card-head">
          <div class="help-card-icon">↻</div>
          <div>
            <h3>Resultados débiles</h3>
            <span class="help-card-tag">Refinar consulta</span>
          </div>
        </div>
        <ul>
          <li>Añade <b>código</b> o revisión vigente.</li>
          <li>Especifica <b>fase</b> del proyecto.</li>
          <li>Cambia términos: <code>accesibilidad</code> → <code>acceso mantenimiento</code>.</li>
        </ul>
        <div class="ex-btns">
          <button type="button" data-q="checklist mantenibilidad fase ejecución diseño cumplimiento">Fase ejecución</button>
          <button type="button" data-q="criterios acceso mantenimiento equipos pesados checklist">Acceso equipos</button>
        </div>
      </article>

    </div>
  </details>
  <div id="status"></div>
  <div id="answer"></div>
  <div id="references"></div>
  <div id="results"></div>
  <p class="meta"><a href="analysis-status.html">Estado de análisis</a> · <a href="corpus-picker.html">Corpus</a></p>
<script>
const q = document.getElementById('q');
const go = document.getElementById('go');
const askBtn = document.getElementById('ask');
const status = document.getElementById('status');
const answerEl = document.getElementById('answer');
const refsEl = document.getElementById('references');
const results = document.getElementById('results');
let lastAsk = null;
let lastSearch = null;

document.querySelectorAll('[data-q]').forEach(b => {
  b.onclick = () => {
    q.value = b.dataset.q;
    if (b.dataset.action === 'search') runSearch();
    else runAsk();
  };
});
go.onclick = runSearch;
askBtn.onclick = runAsk;
q.addEventListener('keydown', e => { if (e.key === 'Enter') runAsk(); });

function apiError(res, fallback) {
  if (res.status === 404) {
    return 'API no disponible (404). Ejecuta: python -m mmi.tools.serve_local --port 8773';
  }
  return fallback || ('HTTP ' + res.status);
}

function showError(err) {
  const hint = location.protocol === 'file:'
    ? ' Abre http://127.0.0.1:8773/search.html (no el archivo HTML directo).'
    : '';
  status.textContent = 'Error: ' + err.message + hint;
}

async function runSearch() {
  const query = q.value.trim();
  if (!query) return;
  status.textContent = 'Buscando…';
  answerEl.innerHTML = '';
  refsEl.innerHTML = '';
  results.innerHTML = '';
  lastAsk = null;
  try {
    const res = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 6 }),
    });
    if (!res.ok) throw new Error(apiError(res));
    const data = await res.json();
    status.textContent = data.count + ' resultados · ' + (data.elapsed_ms || '?') + ' ms';
    lastSearch = { results: data.results || [], loaded: false };
    mountSearchResultsPlaceholder(data.count || 0);
  } catch (err) {
    showError(err);
  }
}

async function fetchAskDetails(section) {
  const res = await fetch('/api/ask-details', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ask_id: lastAsk.ask_id, section }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(apiError(res, err.error));
  }
  return res.json();
}

async function runAsk() {
  const query = q.value.trim();
  if (!query) return;
  status.textContent = 'Buscando evidencia y generando respuesta (OpenRouter)…';
  answerEl.innerHTML = '';
  refsEl.innerHTML = '';
  results.innerHTML = '';
  lastSearch = null;
  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 6 }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(apiError(res, err.error));
    }
    const data = await res.json();
    lastAsk = {
      ask_id: data.ask_id,
      cited_indices: data.cited_indices || [],
      evidence_count: data.evidence_count || 0,
      cited_count: data.cited_count || 0,
      refsLoaded: false,
      evidenceLoaded: false,
    };
    status.textContent = lastAsk.cited_count + ' referencias · ' + lastAsk.evidence_count
      + ' evidencias · ' + (data.elapsed_ms || '?') + ' ms · ' + esc(data.model||'');
    answerEl.innerHTML = renderAnswer(data.answer || '');
    mountReferencesPlaceholder(lastAsk.cited_count);
    mountEvidencePlaceholder(lastAsk.evidence_count);
  } catch (err) {
    showError(err);
  }
}

function linkCites(s) {
  return s.replace(/\\[(\\d+)\\]/g, '<a class="cite-link" href="#ref-$1">[$1]</a>');
}

function renderAnswer(text) {
  if (!text) return '';
  const lines = esc(text).split('\\n');
  const parts = [];
  let inList = false;
  for (const line of lines) {
    const h = line.match(/^## (.+)$/);
    if (h) {
      if (inList) { parts.push('</ul>'); inList = false; }
      parts.push('<h3>' + h[1] + '</h3>');
      continue;
    }
    const li = line.match(/^- (.+)$/);
    if (li) {
      if (!inList) { parts.push('<ul>'); inList = true; }
      parts.push('<li>' + linkCites(li[1]) + '</li>');
      continue;
    }
    if (inList) { parts.push('</ul>'); inList = false; }
    if (line.trim()) parts.push('<p>' + linkCites(line) + '</p>');
  }
  if (inList) parts.push('</ul>');
  return '<div class="answer-box"><h2>Respuesta</h2><div class="answer-body">' + parts.join('') + '</div></div>';
}

function openPanel(id) {
  const panel = document.getElementById(id);
  if (panel) panel.open = true;
  return panel;
}

document.addEventListener('click', async e => {
  const link = e.target.closest('a.cite-link');
  if (!link || !lastAsk) return;
  e.preventDefault();
  try {
    const panel = openPanel('refs-panel');
    if (panel && !lastAsk.refsLoaded) await loadReferences(panel);
    const target = document.getElementById(link.getAttribute('href').slice(1));
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (err) {
    showError(err);
  }
});

async function loadReferences(panel) {
  const hint = panel.querySelector('.lazy-status');
  if (hint) hint.textContent = 'Cargando referencias…';
  const data = await fetchAskDetails('references');
  lastAsk.refsLoaded = true;
  const open = panel.open;
  renderReferences(data.references || []);
  const next = document.getElementById('refs-panel');
  if (next) next.open = open;
}

async function loadEvidence(panel) {
  const hint = panel.querySelector('.lazy-status');
  if (hint) hint.textContent = 'Cargando fragmentos…';
  const data = await fetchAskDetails('evidence');
  lastAsk.evidenceLoaded = true;
  const open = panel.open;
  renderHits(data.results || [], new Set(data.cited_indices || []));
  const next = document.getElementById('evidence-panel');
  if (next) next.open = open;
}

function mountReferencesPlaceholder(count) {
  if (!count) { refsEl.innerHTML = ''; return; }
  refsEl.innerHTML = '<details class="optional-panel" id="refs-panel">'
    + '<summary>Referencias citadas (' + count + ') — clic para cargar</summary>'
    + '<p class="lazy-status">Sin cargar.</p></details>';
  refsEl.querySelector('details').addEventListener('toggle', async ev => {
    const panel = ev.currentTarget;
    if (!panel.open || !lastAsk || lastAsk.refsLoaded) return;
    try { await loadReferences(panel); } catch (err) { showError(err); }
  });
}

function mountEvidencePlaceholder(count) {
  if (!count) { results.innerHTML = ''; return; }
  results.innerHTML = '<details class="optional-panel evidence" id="evidence-panel">'
    + '<summary>Fragmentos de evidencia (' + count + ') — clic para cargar</summary>'
    + '<p class="lazy-status">Sin cargar.</p></details>';
  results.querySelector('details').addEventListener('toggle', async ev => {
    const panel = ev.currentTarget;
    if (!panel.open || !lastAsk || lastAsk.evidenceLoaded) return;
    try { await loadEvidence(panel); } catch (err) { showError(err); }
  });
}

function mountSearchResultsPlaceholder(count) {
  if (!count) { results.innerHTML = ''; return; }
  results.innerHTML = '<details class="optional-panel evidence" id="evidence-panel">'
    + '<summary>Resultados (' + count + ') — clic para cargar</summary>'
    + '<p class="lazy-status">Sin cargar.</p></details>';
  results.querySelector('details').addEventListener('toggle', ev => {
    const panel = ev.currentTarget;
    if (!panel.open || !lastSearch || lastSearch.loaded) return;
    lastSearch.loaded = true;
    const open = panel.open;
    renderHits(lastSearch.results);
    const next = document.getElementById('evidence-panel');
    if (next) next.open = open;
  });
}

function renderReferences(refs) {
  if (!refs.length) { refsEl.innerHTML = ''; return; }
  refsEl.innerHTML = '<details class="optional-panel" id="refs-panel" open>'
    + '<summary>Referencias citadas (' + refs.length + ')</summary>'
    + '<ol class="refs-list">'
    + refs.map(r => `
      <li id="ref-${r.index}" class="cited">
        <span class="ref-num">[${r.index}]</span>
        <strong>${esc(r.citation || r.titulo || 'Fuente')}</strong>
        <div class="ref-meta">${esc([r.tipo, r.version_label, r.section_path,
          r.page_start ? 'pág. ' + r.page_start + (r.page_end && r.page_end !== r.page_start ? '–' + r.page_end : '') : ''
        ].filter(Boolean).join(' · '))}</div>
        ${r.snippet ? '<div class="ref-snippet">“' + esc(r.snippet) + '…”</div>' : ''}
      </li>`).join('')
    + '</ol></details>';
}

function renderHits(hits, citedSet) {
  citedSet = citedSet || new Set();
  if (!hits.length) { results.innerHTML = ''; return; }
  const inner = hits.map((r, i) => {
    const n = i + 1;
    const cited = citedSet.has(n);
    return `
      <div class="hit${cited ? ' cited' : ''}" id="evidence-${n}">
        <h3>${n}. ${esc(r.citation || r.titulo || 'Resultado')}${cited ? ' <span class="badge">citada</span>' : ''}</h3>
        <div>
          <span class="badge">${esc(r.tipo||'')}</span>
          <span class="badge ${r.criticality_level==='seguridad'?'seg':''}">${esc(r.criticality_level||'')}</span>
          <span class="badge">score ${r.score}</span>
        </div>
        <p class="cite">${esc(r.citation||'')}</p>
        <div class="snippet">${esc(r.content||'')}</div>
      </div>`;
  }).join('');
  const label = citedSet.size
    ? 'Fragmentos de evidencia (' + hits.length + ')'
    : 'Resultados (' + hits.length + ')';
  results.innerHTML = '<details class="optional-panel evidence" id="evidence-panel" open>'
    + '<summary>' + label + '</summary>' + inner + '</details>';
}
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
</script>
</body>
</html>"""


from mmi.search.answer import ask as rag_ask
from mmi.search.api_payloads import ask_details_payload, ask_payload
from mmi.search.session import AskSession, AskSessionStore


def make_handler(engine: HybridSearchEngine, html: str):
    sessions = AskSessionStore()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            print(f"[search] {args[0]}")

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"/", "/index.html", "/search.html"}:
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self) -> None:
            import time

            path = urlparse(self.path).path
            if path not in {"/api/search", "/api/ask", "/api/ask-details"}:
                self.send_error(404)
                return

            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
                t0 = time.perf_counter()

                if path == "/api/ask-details":
                    session_id = (data.get("ask_id") or "").strip()
                    section = (data.get("section") or "").strip()
                    session = sessions.get(session_id)
                    if session is None:
                        body = json.dumps({"error": "Sesión expirada o inválida"}, ensure_ascii=False).encode("utf-8")
                        self.send_response(404)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        return
                    payload = ask_details_payload(session, section, _result_dict)
                    payload["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
                else:
                    query = (data.get("query") or "").strip()
                    limit = int(data.get("limit") or 6)

                    if path == "/api/search":
                        hits = engine.search(query, limit=limit)
                        elapsed = int((time.perf_counter() - t0) * 1000)
                        payload = {
                            "query": query,
                            "count": len(hits),
                            "elapsed_ms": elapsed,
                            "results": [_result_dict(r) for r in hits],
                        }
                    else:
                        result = rag_ask(query, engine, limit=limit)
                        session_id = sessions.put(
                            AskSession(
                                query=result.query,
                                hits=result.hits,
                                cited_indices=result.cited_indices,
                                references=result.references,
                            )
                        )
                        payload = ask_payload(result, session_id, int((time.perf_counter() - t0) * 1000))

                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:  # noqa: BLE001
                body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Búsqueda híbrida MMI")
    parser.add_argument("query", nargs="?", help="Consulta (modo CLI)")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--serve", action="store_true", help="UI web en http://127.0.0.1:PORT")
    parser.add_argument("--port", type=int, default=8773)
    parser.add_argument("--ask", action="store_true", help="Generar respuesta con OpenRouter")
    parser.add_argument("--write-html", type=Path, help="Escribe HTML estático en out/")
    args = parser.parse_args(argv)

    load_dotenv()

    if args.write_html:
        args.write_html.parent.mkdir(parents=True, exist_ok=True)
        args.write_html.write_text(render_search_html(), encoding="utf-8")
        print(f"HTML → {args.write_html.resolve()}")
        if not args.serve and not args.query:
            return 0

    engine = HybridSearchEngine(tenant_slug=args.tenant)

    if args.serve:
        html = render_search_html()
        out = Path("out/search.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        handler = make_handler(engine, html)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        print(f"Abre http://127.0.0.1:{args.port}/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nDetenido.")
        return 0

    if not args.query:
        parser.print_help()
        return 1

    if args.ask:
        from mmi.search.answer import ask as rag_ask

        result = rag_ask(args.query, engine, limit=args.limit)
        print(f"\nModelo: {result.model}\n")
        print(result.answer)
        if result.references:
            print("\n--- Referencias citadas ---")
            for ref in result.references:
                cite = ref.get("citation") or ref.get("titulo")
                meta = " · ".join(
                    x
                    for x in [
                        ref.get("tipo"),
                        ref.get("version_label"),
                        ref.get("section_path"),
                    ]
                    if x
                )
                print(f"  [{ref['index']}] {cite}" + (f" ({meta})" if meta else ""))
        elif result.sources:
            print("\n--- Fuentes consultadas ---")
            for s in result.sources:
                print(f"  [{s['index']}] {s.get('citation') or s.get('titulo')}")
        return 0

    hits = engine.search(args.query, limit=args.limit)
    for i, r in enumerate(hits, 1):
        print(f"\n{i}. [{r.score:.3f}] {r.citation}")
        print(f"   {r.content[:200]}…")
    if not hits:
        print("Sin resultados.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
