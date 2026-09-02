"""Pagina de busqueda hibrida — shell vitrina o tema dev."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from mmi.search.examples import _CATEGORIES, _TIPS, load_corpus_stats
from mmi.search.vitrina_examples import vitrina_example_card
from mmi.web.vitrina import PROJECT_SHORT
from mmi.web.vitrina_shell import render_shell


def _vitrina_example_card(cat: dict[str, Any]) -> str:
    return vitrina_example_card(cat)


def render_search_vitrina_html(out_dir: Path | None = None) -> str:
    stats = load_corpus_stats(out_dir)
    docs = stats.get("docs") or "—"
    chunks = stats.get("chunks") or 0
    tokens = stats.get("tokens_fmt") or ""
    lote = str(stats.get("lote") or "ODS1")
    chunks_k = f"{chunks // 1000}k" if isinstance(chunks, int) and chunks >= 1000 else str(chunks or "—")

    corpus_cards = "".join(_vitrina_example_card(c) for c in _CATEGORIES)
    tip_cards = "".join(_vitrina_example_card(c) for c in _TIPS)

    content = f"""
<div class="bg-surface-container-lowest rounded-xl border border-outline/20 p-stack-lg shadow-sm">
  <div class="flex flex-col lg:flex-row gap-stack-md">
    <div class="flex-1 flex items-center gap-stack-sm bg-surface-container-low px-stack-md py-2 rounded-full border border-outline/30">
      <span class="material-symbols-outlined text-outline shrink-0">search</span>
      <input id="q" type="search" placeholder="Términos, códigos, checklist, FMECA, matriz MRI…"
        class="flex-1 min-w-0 bg-transparent border-none focus:ring-0 text-body-md text-on-surface placeholder:text-on-surface-variant"/>
    </div>
    <div class="flex flex-wrap gap-stack-sm shrink-0">
      <button id="go" type="button"
        class="inline-flex items-center gap-base bg-primary text-on-primary px-stack-lg py-stack-md rounded-lg text-label-sm font-bold uppercase tracking-wide hover:opacity-95 transition-opacity">
        <span class="material-symbols-outlined" style="font-size:18px">search</span>
        Buscar
      </button>
      <button id="ask" type="button"
        class="inline-flex items-center gap-base bg-secondary-container text-on-secondary-container px-stack-lg py-stack-md rounded-lg text-label-sm font-bold uppercase tracking-wide hover:opacity-95 transition-opacity">
        <span class="material-symbols-outlined" style="font-size:18px">psychology</span>
        Consulta RAG
      </button>
    </div>
  </div>
  <p class="text-body-md text-on-surface-variant mt-stack-md">
    Búsqueda híbrida Qdrant + Supabase · respuestas con citas en
    <a href="/rag.html" class="text-primary font-semibold hover:underline">Consulta RAG</a>.
    Al buscar verá <strong class="text-on-surface">Analizando…</strong> — espere el resultado.
  </p>
</div>

<div class="bg-surface-container-low p-stack-md rounded-xl border border-outline/20 text-body-md text-on-surface-variant">
  Corpus indexado: <strong class="text-primary">{docs}</strong> documentos ·
  <strong class="text-primary">{chunks_k}</strong> fragmentos ·
  <strong class="text-primary">{tokens or "—"}</strong> tokens
</div>

<div id="status" class="text-body-md text-on-surface-variant min-h-[1.25rem]"></div>
<div id="analyzing" class="hidden bg-surface-container-lowest rounded-xl border border-outline/20 p-stack-lg shadow-sm">
  <div class="flex items-center gap-stack-md">
    <div class="w-12 h-12 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center animate-pulse shrink-0">
      <span class="material-symbols-outlined">hourglass_top</span>
    </div>
    <div>
      <p class="text-body-lg font-semibold text-primary">Analizando…</p>
      <p class="text-body-md text-on-surface-variant">Recuperando fragmentos del corpus. Espere un momento.</p>
    </div>
  </div>
  <div class="mt-stack-md h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
    <div class="h-full bg-primary rounded-full animate-pulse" style="width:65%"></div>
  </div>
</div>
<div id="results" class="space-y-stack-md"></div>

<details class="bg-surface-container-lowest rounded-xl border border-outline/20 overflow-hidden group" open>
  <summary class="cursor-pointer list-none px-stack-lg py-stack-md flex items-center justify-between gap-stack-md border-b border-outline/10">
    <div>
      <h2 class="text-headline-md font-semibold text-primary">Ejemplos del corpus</h2>
      <p class="text-body-md text-on-surface-variant mt-1">Clic azul → Consulta RAG · verde → buscar aquí. Espere <strong class="text-on-surface">Analizando…</strong> antes del resultado.</p>
    </div>
    <span class="material-symbols-outlined text-outline group-open:rotate-180 transition-transform">expand_more</span>
  </summary>
  <div class="p-stack-lg grid grid-cols-1 md:grid-cols-2 gap-gutter">{corpus_cards}</div>
</details>

<details class="bg-surface-container-lowest rounded-xl border border-outline/20 overflow-hidden group">
  <summary class="cursor-pointer list-none px-stack-lg py-stack-md flex items-center justify-between gap-stack-md border-b border-outline/10">
    <div>
      <h2 class="text-headline-md font-semibold text-primary">Consejos de búsqueda</h2>
      <p class="text-body-md text-on-surface-variant mt-1">Cómo formular preguntas y cuándo usar cada modo</p>
    </div>
    <span class="material-symbols-outlined text-outline group-open:rotate-180 transition-transform">expand_more</span>
  </summary>
  <div class="p-stack-lg grid grid-cols-1 md:grid-cols-2 gap-gutter">{tip_cards}</div>
</details>"""

    scripts = """
<script>
const q = document.getElementById('q');
const go = document.getElementById('go');
const askBtn = document.getElementById('ask');
const status = document.getElementById('status');
const analyzing = document.getElementById('analyzing');
const results = document.getElementById('results');
let lastSearch = null;
const MIN_ANALYZE_MS = 1400;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function setAnalyzing(on) {
  if (!analyzing) return;
  analyzing.classList.toggle('hidden', !on);
}

function goRag(query) {
  const text = (query != null ? query : q.value).trim();
  if (!text) return;
  location.href = '/rag.html?q=' + encodeURIComponent(text);
}

document.querySelectorAll('[data-q]').forEach(b => {
  b.onclick = () => {
    q.value = b.dataset.q;
    if (b.dataset.action === 'search') runSearch();
    else goRag(b.dataset.q);
  };
});
go.onclick = runSearch;
askBtn.onclick = () => goRag();
q.addEventListener('keydown', e => { if (e.key === 'Enter') runSearch(); });

async function apiError(res, fallback) {
  if (res.status === 404) {
    return 'API no disponible (404). Ejecuta: python -m mmi.tools.serve_local --port 8773';
  }
  try {
    const data = await res.json();
    if (data.error) return data.error + (data.hint ? ' · ' + data.hint : '');
  } catch (_) {}
  return fallback || ('HTTP ' + res.status);
}

function showError(err) {
  setAnalyzing(false);
  const hint = location.protocol === 'file:'
    ? ' Abre http://127.0.0.1:8773/search.html (no el archivo HTML directo).'
    : '';
  status.textContent = 'Error: ' + err.message + hint;
  status.className = 'text-body-md text-error font-semibold min-h-[1.25rem]';
}

async function runSearch() {
  const query = q.value.trim();
  if (!query) return;
  const started = Date.now();
  status.textContent = 'Analizando…';
  status.className = 'text-body-md text-primary font-semibold min-h-[1.25rem]';
  results.innerHTML = '';
  setAnalyzing(true);
  lastSearch = null;
  go.disabled = true;
  try {
    const res = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 8 }),
    });
    if (!res.ok) throw new Error(await apiError(res));
    const data = await res.json();
    const wait = Math.max(0, MIN_ANALYZE_MS - (Date.now() - started));
    if (wait) await sleep(wait);
    setAnalyzing(false);
    status.textContent = data.count + ' resultados · ' + (data.elapsed_ms || '?') + ' ms';
    status.className = 'text-body-md text-primary font-semibold min-h-[1.25rem]';
    lastSearch = { results: data.results || [], loaded: false };
    mountSearchResultsPlaceholder(data.count || 0);
  } catch (err) {
    showError(err);
  } finally {
    go.disabled = false;
  }
}

function mountSearchResultsPlaceholder(count) {
  if (!count) {
    results.innerHTML = '<div class="bg-surface-container-lowest rounded-xl border border-outline/20 p-stack-lg text-body-md text-on-surface-variant">Sin resultados para esta consulta.</div>';
    return;
  }
  loadSearchResults();
}

async function loadSearchResults() {
  if (!lastSearch || lastSearch.loaded) return;
  lastSearch.loaded = true;
  renderHits(lastSearch.results);
}

function badge(text, extra) {
  const cls = extra ? 'bg-secondary-fixed/40 text-on-secondary-fixed border-secondary/20' : 'bg-tertiary-fixed text-on-surface-variant border-outline/20';
  return '<span class="inline-flex items-center px-stack-sm py-0.5 rounded border text-label-sm font-semibold mr-1 mb-1 ' + cls + '">' + esc(text) + '</span>';
}

function renderHits(hits) {
  if (!hits.length) {
    results.innerHTML = '';
    return;
  }
  const inner = hits.map((r, i) => {
    const n = i + 1;
    const seg = r.criticality_level === 'seguridad';
    return `
      <article class="bg-surface-container-lowest rounded-xl border border-outline/20 p-stack-lg shadow-sm hover:border-primary/30 transition-colors" id="evidence-${n}">
        <div class="flex items-start justify-between gap-stack-md mb-stack-sm">
          <h3 class="text-body-lg font-bold text-primary">${n}. ${esc(r.citation || r.titulo || 'Resultado')}</h3>
          <span class="text-label-sm font-semibold text-on-surface-variant shrink-0">${r.score}</span>
        </div>
        <div class="mb-stack-sm">${badge(r.tipo || '', false)}${badge(r.criticality_level || '', seg)}</div>
        <p class="text-body-md text-primary/80 mb-stack-sm">${esc(r.citation || '')}</p>
        <div class="text-body-md text-on-surface-variant leading-relaxed whitespace-pre-wrap">${esc(r.content || '')}</div>
        <p class="mt-stack-md">
          <a href="/rag.html?q=${encodeURIComponent(q.value.trim())}" class="inline-flex items-center gap-base text-label-sm font-semibold text-secondary hover:underline">
            Preguntar sobre esto en Consulta RAG
            <span class="material-symbols-outlined text-base">arrow_forward</span>
          </a>
        </p>
      </article>`;
  }).join('');
  results.innerHTML = '<div class="bg-surface-container-lowest rounded-xl border border-outline/20 overflow-hidden">'
    + '<div class="px-stack-lg py-stack-md border-b border-outline/10 flex items-center justify-between">'
    + '<h2 class="text-headline-md font-semibold text-primary">Resultados (' + hits.length + ')</h2>'
    + '</div><div class="p-stack-lg space-y-stack-md">' + inner + '</div></div>';
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

(function boot() {
  const params = new URLSearchParams(location.search);
  const initial = params.get('q');
  if (initial) {
    q.value = initial;
    runSearch();
  } else {
    q.focus();
  }
})();
</script>"""

    return render_shell(
        active="search",
        title="Búsqueda híbrida",
        header_subtitle=f"{PROJECT_SHORT} · {docs} documentos",
        content=content,
        corpus_lote=PROJECT_SHORT,
        footer_scripts=scripts,
    )
