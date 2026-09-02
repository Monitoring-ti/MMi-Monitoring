"""Pantalla dedicada para respuestas RAG con citas."""

from __future__ import annotations

from pathlib import Path


def render_rag_vitrina_html(out_dir: Path | None = None) -> str:
    from mmi.search.examples import _CATEGORIES, _TIPS, load_corpus_stats
    from mmi.search.vitrina_examples import vitrina_example_card
    from mmi.web.vitrina import PROJECT_SHORT
    from mmi.web.vitrina_shell import render_shell

    stats = load_corpus_stats(out_dir)
    docs = stats.get("docs") or "—"
    chunks = stats.get("chunks") or 0
    tokens = stats.get("tokens_fmt") or ""
    lote = str(stats.get("lote") or "ODS1")
    chunks_k = f"{chunks // 1000}k" if isinstance(chunks, int) and chunks >= 1000 else str(chunks or "—")

    quick_examples = "".join(
        vitrina_example_card(c)
        for c in (*_CATEGORIES[:3], *_TIPS[:1])
    )

    extra_head = """
<style>
  .answer-body h3 { margin: 1rem 0 0.5rem; font-size: 0.98rem; font-weight: 600; color: #002a6d; }
  .answer-body h3:first-child { margin-top: 0; }
  .answer-body p { margin: 0 0 0.75rem; line-height: 1.6; color: #434651; }
  .answer-body ul { margin: 0 0 0.75rem; padding-left: 1.25rem; color: #434651; line-height: 1.55; }
  .answer-body li { margin-bottom: 0.35rem; }
  .cite-link { color: #002a6d; font-weight: 600; text-decoration: none; }
  .cite-link:hover { text-decoration: underline; }
  .refs-list { margin: 0; padding: 0; list-style: none; }
  .refs-list li { scroll-margin-top: 5rem; }
</style>"""

    content = f"""
<div class="bg-surface-container-lowest rounded-xl border border-outline/20 p-stack-lg shadow-sm">
  <div class="flex flex-col lg:flex-row gap-stack-md">
    <div class="flex-1 flex items-center gap-stack-sm bg-surface-container-low px-stack-md py-2 rounded-full border border-outline/30">
      <span class="material-symbols-outlined text-outline shrink-0">psychology</span>
      <input id="q" type="search" placeholder="Pregunta completa: definición, criterio, procedimiento, checklist…"
        class="flex-1 min-w-0 bg-transparent border-none focus:ring-0 text-body-md text-on-surface placeholder:text-on-surface-variant"/>
    </div>
    <div class="flex flex-wrap gap-stack-sm shrink-0">
      <button id="ask" type="button"
        class="inline-flex items-center gap-base bg-primary text-on-primary px-stack-lg py-stack-md rounded-lg text-label-sm font-bold uppercase tracking-wide hover:opacity-95 transition-opacity disabled:opacity-50">
        <span class="material-symbols-outlined" style="font-size:18px">auto_awesome</span>
        Preguntar
      </button>
      <button id="clear" type="button"
        class="inline-flex items-center gap-base bg-surface-container-high text-on-surface-variant px-stack-lg py-stack-md rounded-lg text-label-sm font-semibold hover:bg-surface-container transition-colors">
        Limpiar
      </button>
    </div>
  </div>
  <p class="text-body-md text-on-surface-variant mt-stack-md">
    Respuesta con <strong class="text-on-surface">OpenRouter</strong> y citas documentales ·
    <a href="/search.html" class="text-primary font-semibold hover:underline">solo fragmentos → Búsqueda</a>.
    Tras preguntar verá <strong class="text-on-surface">Analizando…</strong> — espere; la generación puede tardar varios segundos.
  </p>
</div>

<div class="bg-surface-container-low p-stack-md rounded-xl border border-outline/20 text-body-md text-on-surface-variant">
  Corpus indexado: <strong class="text-primary">{docs}</strong> documentos ·
  <strong class="text-primary">{chunks_k}</strong> fragmentos ·
  <strong class="text-primary">{tokens or "—"}</strong> tokens
</div>

<div id="question" class="bg-primary-fixed/20 border border-primary-fixed rounded-xl p-stack-lg hidden">
  <span class="block text-label-sm font-semibold uppercase tracking-wider text-primary mb-base">Consulta</span>
  <span id="question-text" class="text-body-lg text-on-surface"></span>
</div>

<div id="status" class="text-body-md text-on-surface-variant min-h-[1.25rem]"></div>
<div id="conflict-banner" class="hidden rounded-xl border border-secondary/30 bg-secondary-fixed/40 p-stack-md text-body-md text-on-secondary-fixed"></div>
<ul id="conflicts" class="hidden space-y-stack-sm mb-stack-md"></ul>

<div class="grid grid-cols-1 lg:grid-cols-3 gap-gutter items-start">
  <section class="lg:col-span-2 bg-surface-container-lowest rounded-xl border border-outline/20 overflow-hidden shadow-sm" aria-live="polite">
    <div class="px-stack-lg py-stack-md border-b border-outline/10 bg-primary-fixed/10">
      <h2 class="text-headline-md font-semibold text-primary">Respuesta</h2>
    </div>
    <div class="p-stack-lg">
      <div id="answer" class="text-body-md text-on-surface-variant italic">Escribe una pregunta y pulsa <strong class="text-on-surface not-italic">Preguntar</strong>, o elige un ejemplo abajo.</div>
    </div>
  </section>
  <aside class="bg-surface-container-lowest rounded-xl border border-outline/20 overflow-hidden shadow-sm">
    <div class="px-stack-lg py-stack-md border-b border-outline/10">
      <h2 class="text-headline-md font-semibold text-primary">Referencias citadas</h2>
    </div>
    <div class="p-stack-md max-h-[70vh] overflow-auto">
      <ol id="references" class="refs-list space-y-stack-sm"></ol>
      <p id="refs-empty" class="text-body-md text-on-surface-variant italic">Las fuentes citadas [1][2]… aparecerán aquí.</p>
    </div>
  </aside>
</div>

<details class="bg-surface-container-lowest rounded-xl border border-outline/20 overflow-hidden group mt-gutter" id="evidence-wrap" open>
  <summary class="cursor-pointer list-none px-stack-lg py-stack-md flex items-center justify-between gap-stack-md border-b border-outline/10">
    <h2 id="evidence-summary" class="text-headline-md font-semibold text-primary">Fragmentos de evidencia</h2>
    <span class="material-symbols-outlined text-outline group-open:rotate-180 transition-transform">expand_more</span>
  </summary>
  <div class="p-stack-lg space-y-stack-md" id="evidence"></div>
</details>

<details class="bg-surface-container-lowest rounded-xl border border-outline/20 overflow-hidden group">
  <summary class="cursor-pointer list-none px-stack-lg py-stack-md flex items-center justify-between gap-stack-md border-b border-outline/10">
    <div>
      <h2 class="text-headline-md font-semibold text-primary">Ejemplos de consulta</h2>
      <p class="text-body-md text-on-surface-variant mt-1">Un clic abre Analizando… y luego la respuesta con citas. Espere el resultado.</p>
    </div>
    <span class="material-symbols-outlined text-outline group-open:rotate-180 transition-transform">expand_more</span>
  </summary>
  <div class="p-stack-lg grid grid-cols-1 md:grid-cols-2 gap-gutter">{quick_examples}</div>
</details>"""

    scripts = """
<script>
const q = document.getElementById('q');
const askBtn = document.getElementById('ask');
const clearBtn = document.getElementById('clear');
const statusEl = document.getElementById('status');
const answerEl = document.getElementById('answer');
const refsEl = document.getElementById('references');
const refsEmpty = document.getElementById('refs-empty');
const evidenceEl = document.getElementById('evidence');
const evidenceSummary = document.getElementById('evidence-summary');
const questionBox = document.getElementById('question');
const questionText = document.getElementById('question-text');
const conflictBannerEl = document.getElementById('conflict-banner');
const conflictsEl = document.getElementById('conflicts');
let lastAsk = null;
const MIN_ANALYZE_MS = 1800;
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function analyzingMarkup() {
  return `
    <div class="flex items-center gap-stack-md not-italic">
      <div class="w-11 h-11 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center animate-pulse shrink-0">
        <span class="material-symbols-outlined">hourglass_top</span>
      </div>
      <div>
        <p class="text-body-lg font-semibold text-primary">Analizando…</p>
        <p class="text-body-md text-on-surface-variant">Recuperando evidencia y generando respuesta con citas. Espere…</p>
      </div>
    </div>
    <div class="mt-stack-md h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
      <div class="h-full bg-primary rounded-full animate-pulse" style="width:70%"></div>
    </div>`;
}

document.querySelectorAll('[data-q]').forEach(b => {
  b.onclick = () => {
    if (b.dataset.action === 'search') {
      location.href = '/search.html?q=' + encodeURIComponent(b.dataset.q);
      return;
    }
    q.value = b.dataset.q;
    runAsk();
  };
});
askBtn.onclick = runAsk;
clearBtn.onclick = clearAll;
q.addEventListener('keydown', e => { if (e.key === 'Enter') runAsk(); });

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function apiError(res, fallback) {
  if (res.status === 404) {
    return 'API no disponible (404). Ejecuta: python -m mmi.tools.serve_local --port 8773';
  }
  return fallback || ('HTTP ' + res.status);
}

function setStatus(text, ok) {
  statusEl.textContent = text;
  statusEl.className = ok
    ? 'text-body-md text-primary font-semibold min-h-[1.25rem]'
    : 'text-body-md text-on-surface-variant min-h-[1.25rem]';
}

function showError(err) {
  const hint = location.protocol === 'file:'
    ? ' Abre http://127.0.0.1:8773/rag.html (no el archivo directo).'
    : '';
  statusEl.textContent = 'Error: ' + err.message + hint;
  statusEl.className = 'text-body-md text-error font-semibold min-h-[1.25rem]';
}

function clearAll() {
  q.value = '';
  lastAsk = null;
  questionBox.classList.add('hidden');
  answerEl.innerHTML = 'Escribe una pregunta y pulsa <strong class="text-on-surface not-italic">Preguntar</strong>, o elige un ejemplo abajo.';
  answerEl.className = 'text-body-md text-on-surface-variant italic';
  refsEl.innerHTML = '';
  refsEmpty.classList.remove('hidden');
  evidenceEl.innerHTML = '';
  evidenceSummary.textContent = 'Fragmentos de evidencia';
  conflictBannerEl.classList.add('hidden');
  conflictBannerEl.textContent = '';
  conflictsEl.classList.add('hidden');
  conflictsEl.innerHTML = '';
  setStatus('', false);
  history.replaceState(null, '', '/rag.html');
}

function linkCites(s) {
  return s.replace(/\\[(\\d+)\\]/g, '<a class="cite-link" href="#ref-$1">[$1]</a>');
}

function renderAnswer(text) {
  if (!text) return '<p class="text-on-surface-variant italic">Sin respuesta.</p>';
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
  return '<div class="answer-body">' + parts.join('') + '</div>';
}

function renderReferences(refs) {
  if (!refs.length) {
    refsEl.innerHTML = '';
    refsEmpty.classList.remove('hidden');
    return;
  }
  refsEmpty.classList.add('hidden');
  refsEl.innerHTML = refs.map(r => `
    <li id="ref-${r.index}" class="bg-surface-container-low rounded-lg border border-primary/20 p-stack-md cited">
      <span class="inline-block min-w-[2rem] font-bold text-primary">[${r.index}]</span>
      <strong class="text-body-md text-on-surface">${esc(r.citation || r.titulo || 'Fuente')}</strong>
      <div class="text-label-sm text-on-surface-variant mt-1">${esc([r.tipo, r.version_label, r.section_path,
        r.page_start ? 'pág. ' + r.page_start + (r.page_end && r.page_end !== r.page_start ? '–' + r.page_end : '') : ''
      ].filter(Boolean).join(' · '))}</div>
      ${r.snippet ? '<div class="text-body-md text-on-surface-variant mt-2 italic">“' + esc(r.snippet) + '…”</div>' : ''}
    </li>`).join('');
}

function badge(text, seg) {
  const cls = seg
    ? 'bg-secondary-fixed/40 text-on-secondary-fixed border-secondary/20'
    : 'bg-tertiary-fixed text-on-surface-variant border-outline/20';
  return '<span class="inline-flex items-center px-stack-sm py-0.5 rounded border text-label-sm font-semibold mr-1 mb-1 ' + cls + '">' + esc(text) + '</span>';
}

function renderHits(hits, citedSet) {
  citedSet = citedSet || new Set();
  if (!hits.length) {
    evidenceEl.innerHTML = '<p class="text-body-md text-on-surface-variant italic">Sin fragmentos recuperados.</p>';
    evidenceSummary.textContent = 'Fragmentos de evidencia (0)';
    return;
  }
  evidenceSummary.textContent = 'Fragmentos de evidencia (' + hits.length + ')';
  evidenceEl.innerHTML = hits.map((r, i) => {
    const n = i + 1;
    const cited = citedSet.has(n);
    const seg = r.criticality_level === 'seguridad';
    return `
      <article class="bg-surface-container-low rounded-xl border p-stack-lg scroll-mt-20 ${cited ? 'border-primary/40' : 'border-outline/20'}" id="evidence-${n}">
        <h3 class="text-body-lg font-bold text-primary mb-stack-sm">${n}. ${esc(r.citation || r.titulo || 'Resultado')}${cited ? ' <span class="text-label-sm font-semibold text-secondary">· citada</span>' : ''}</h3>
        <div class="mb-stack-sm">${badge(r.tipo || '', false)}${badge(r.criticality_level || '', seg)}<span class="text-label-sm text-on-surface-variant">score ${r.score}</span></div>
        <div class="text-body-md text-on-surface-variant leading-relaxed whitespace-pre-wrap">${esc(r.content || '')}</div>
      </article>`;
  }).join('');
}

function renderConflicts(banner, conflictos) {
  conflictos = conflictos || [];
  if (!banner || !banner.visible || !conflictos.length) {
    conflictBannerEl.classList.add('hidden');
    conflictBannerEl.textContent = '';
    conflictsEl.classList.add('hidden');
    conflictsEl.innerHTML = '';
    return;
  }
  const info = banner.severity !== 'warn';
  conflictBannerEl.className = info
    ? 'rounded-xl border border-primary/20 bg-primary-fixed/20 p-stack-md text-body-md text-primary'
    : 'rounded-xl border border-secondary/30 bg-secondary-fixed/40 p-stack-md text-body-md text-on-secondary-fixed';
  conflictBannerEl.textContent = banner.message || ('Conflicto documental detectado (' + conflictos.length + ')');
  conflictBannerEl.classList.remove('hidden');
  conflictsEl.classList.remove('hidden');
  conflictsEl.innerHTML = conflictos.map(c => `
    <li class="rounded-lg border p-stack-md text-body-md ${c.severity === 'info' ? 'border-primary/20 bg-primary-fixed/10 text-primary' : 'border-secondary/30 bg-secondary-fixed/30 text-on-secondary-fixed'}">
      <div class="text-label-sm font-semibold uppercase tracking-wider mb-1">${esc(c.kind || 'conflicto')}</div>
      ${esc(c.text || '')}
    </li>`).join('');
}

document.addEventListener('click', e => {
  const link = e.target.closest('a.cite-link');
  if (!link) return;
  e.preventDefault();
  const target = document.getElementById(link.getAttribute('href').slice(1));
  if (target) target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
});

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
  const started = Date.now();
  askBtn.disabled = true;
  setStatus('Analizando…', false);
  answerEl.innerHTML = analyzingMarkup();
  answerEl.className = '';
  refsEl.innerHTML = '';
  refsEmpty.classList.add('hidden');
  evidenceEl.innerHTML = '<p class="text-on-surface-variant italic">Analizando evidencia…</p>';
  conflictBannerEl.classList.add('hidden');
  conflictsEl.classList.add('hidden');
  questionBox.classList.remove('hidden');
  questionText.textContent = query;
  history.replaceState(null, '', '/rag.html?q=' + encodeURIComponent(query));
  try {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 8 }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(apiError(res, err.error));
    }
    const data = await res.json();
    const wait = Math.max(0, MIN_ANALYZE_MS - (Date.now() - started));
    if (wait) await sleep(wait);
    lastAsk = { ask_id: data.ask_id, cited_indices: data.cited_indices || [] };
    answerEl.innerHTML = renderAnswer(data.answer || '');
    answerEl.className = '';
    renderConflicts(data.conflict_banner, data.conflictos);
    setStatus(
      data.cited_count + ' referencias · ' + data.evidence_count + ' evidencias · '
      + (data.elapsed_ms || '?') + ' ms · ' + (data.model || ''),
      true
    );
    const citedSet = new Set(data.cited_indices || []);
    const [refsData, evData] = await Promise.all([
      fetchAskDetails('references'),
      fetchAskDetails('evidence'),
    ]);
    renderReferences(refsData.references || []);
    renderHits(evData.results || [], citedSet);
  } catch (err) {
    showError(err);
    answerEl.innerHTML = '<p class="text-on-surface-variant italic">No se pudo generar la respuesta.</p>';
    evidenceEl.innerHTML = '';
  } finally {
    askBtn.disabled = false;
  }
}

(function boot() {
  const params = new URLSearchParams(location.search);
  const initial = params.get('q');
  if (initial) {
    q.value = initial;
    runAsk();
  } else {
    q.focus();
  }
})();
</script>"""

    return render_shell(
        active="rag",
        title="Consulta RAG",
        header_subtitle=f"{PROJECT_SHORT} · respuestas con citas",
        content=content,
        corpus_lote=PROJECT_SHORT,
        extra_head=extra_head,
        footer_scripts=scripts,
        show_fab=False,
    )


def render_rag_html(out_dir: Path | None = None) -> str:
    from mmi.web.deploy_mode import is_vitrina

    if is_vitrina():
        return render_rag_vitrina_html(out_dir)

    from mmi.analysis.review_shell import render_review_nav, review_nav_css
    from mmi.search.examples import load_corpus_stats, render_corpus_intro

    stats = load_corpus_stats(out_dir)
    intro = render_corpus_intro(stats)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MMI — Consulta RAG</title>
<style>
  :root {{
    font-family: Segoe UI, system-ui, sans-serif;
    color: #e8e8e8;
    background: #1a1a1a;
    --rag-accent: #8fddb0;
    --rag-panel: #1a241a;
    --rag-border: #2d4a2d;
    --ref-panel: #151a24;
    --ref-border: #2a3344;
  }}
  body {{ margin: 0; padding: 20px 24px 48px; max-width: 1180px; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 6px; }}
  .meta {{ color: #9a9a9a; margin-bottom: 14px; font-size: 0.9rem; }}
  .meta a {{ color: #8ab4ff; }}
  .bar {{
    display: flex; gap: 8px; margin-bottom: 12px; position: sticky; top: 0; z-index: 5;
    padding: 10px 0; background: linear-gradient(#1a1a1a 70%, transparent);
  }}
  input[type=search] {{
    flex: 1; padding: 12px 14px; border-radius: 10px; border: 1px solid #444;
    background: #111; color: #eee; font-size: 1rem;
  }}
  button {{
    padding: 12px 18px; border-radius: 10px; border: none; background: #2a2a2a;
    color: #fff; font-weight: 600; cursor: pointer; border: 1px solid #444;
  }}
  button.primary {{ background: #2b5cff; border-color: #2b5cff; }}
  button.ghost {{ background: transparent; font-weight: 500; }}
  button:hover {{ filter: brightness(1.08); }}
  button:disabled {{ opacity: 0.55; cursor: wait; }}
  .corpus-stats {{ color: #b8c8e0; font-size: 0.86rem; margin: 0 0 16px; line-height: 1.5;
    padding: 10px 14px; border-radius: 8px; background: #1a2438; border: 1px solid #2a3a5a; }}
  .question-box {{
    margin: 0 0 14px; padding: 12px 16px; border-radius: 10px;
    background: #222; border: 1px solid #333; font-size: 1.02rem; line-height: 1.45;
  }}
  .question-box .label {{ display: block; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.04em; color: #8ab4ff; margin-bottom: 6px; }}
  #status {{ color: #9a9a9a; margin-bottom: 14px; font-size: 0.88rem; min-height: 1.2em; }}
  #status.ok {{ color: #8fddb0; }}
  .layout {{
    display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(280px, 1fr);
    gap: 16px; align-items: start;
  }}
  @media (max-width: 900px) {{ .layout {{ grid-template-columns: 1fr; }} }}
  .panel {{
    border-radius: 12px; border: 1px solid #333; background: #202020;
    overflow: hidden; min-height: 120px;
  }}
  .panel-head {{
    padding: 10px 14px; font-size: 0.82rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.03em; border-bottom: 1px solid #333; color: #b0b0b0;
  }}
  .panel-body {{ padding: 16px; }}
  .answer-panel {{ border-color: var(--rag-border); background: var(--rag-panel); }}
  .answer-panel .panel-head {{ color: var(--rag-accent); border-color: var(--rag-border); background: #152018; }}
  .answer-body h3 {{ margin: 16px 0 8px; font-size: 0.98rem; color: #b8e6c8; }}
  .answer-body h3:first-child {{ margin-top: 0; }}
  .answer-body p {{ margin: 0 0 12px; line-height: 1.6; color: #e4e4e4; }}
  .answer-body ul {{ margin: 0 0 12px; padding-left: 20px; color: #ddd; line-height: 1.55; }}
  .answer-body li {{ margin-bottom: 6px; }}
  .answer-empty {{ color: #7a7a7a; font-style: italic; line-height: 1.5; }}
  .refs-panel .panel-body {{ padding: 10px 12px; max-height: 70vh; overflow: auto; }}
  .refs-list {{ margin: 0; padding: 0; list-style: none; }}
  .refs-list li {{
    margin-bottom: 10px; padding: 10px 12px; border-radius: 8px;
    background: var(--ref-panel); border: 1px solid var(--ref-border); font-size: 0.86rem;
    line-height: 1.4; scroll-margin-top: 80px;
  }}
  .refs-list li.cited {{ border-color: #3d5a8a; }}
  .ref-num {{ display: inline-block; min-width: 2rem; font-weight: 700; color: #8ab4ff; }}
  .ref-meta {{ color: #8a9ab0; font-size: 0.78rem; margin-top: 4px; }}
  .ref-snippet {{ color: #9aa8bc; font-size: 0.8rem; margin-top: 6px; font-style: italic; }}
  .cite-link {{ color: #8ab4ff; text-decoration: none; font-weight: 600; }}
  .cite-link:hover {{ text-decoration: underline; }}
  .evidence-section {{ margin-top: 16px; }}
  details.evidence {{
    border: 1px solid #333; border-radius: 12px; background: #1c1c1c; overflow: hidden;
  }}
  details.evidence > summary {{
    cursor: pointer; padding: 12px 16px; font-weight: 600; color: #b0b0b0;
    list-style: none;
  }}
  details.evidence > summary::-webkit-details-marker {{ display: none; }}
  details.evidence[open] > summary {{ border-bottom: 1px solid #333; }}
  .evidence-inner {{ padding: 12px 16px 16px; }}
  .hit {{
    border: 1px solid #333; border-radius: 8px; padding: 14px; margin-bottom: 12px;
    background: #202020; scroll-margin-top: 80px;
  }}
  .hit.cited {{ border-color: #3d5a8a; }}
  .hit h3 {{ margin: 0 0 6px; font-size: 0.92rem; color: #d4e4ff; }}
  .badge {{
    font-size: 0.72rem; padding: 2px 7px; border-radius: 999px;
    background: #2a2a2a; color: #aaa; margin-right: 6px;
  }}
  .badge.seg {{ background: #3d321a; color: #e6c07b; }}
  .snippet {{ color: #ccc; font-size: 0.86rem; line-height: 1.45; white-space: pre-wrap; margin-top: 8px; }}
  .conflict-banner {{
    margin: 0 0 14px; padding: 12px 16px; border-radius: 10px; font-size: 0.9rem; line-height: 1.45;
    border: 1px solid #5a4a1a; background: #2a2410; color: #f0d890;
  }}
  .conflict-banner.info {{ border-color: #2a4a5a; background: #152028; color: #9ac8e0; }}
  .conflict-list {{
    margin: 0 0 14px; padding: 0; list-style: none;
  }}
  .conflict-list li {{
    margin-bottom: 8px; padding: 10px 14px; border-radius: 8px;
    border: 1px solid #4a3a18; background: #221c10; font-size: 0.86rem; line-height: 1.4;
  }}
  .conflict-list li.info {{ border-color: #2a3a4a; background: #141c24; }}
  .conflict-kind {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; color: #c8a860; }}
  .conflict-list li.info .conflict-kind {{ color: #7ab0d0; }}
  .examples {{ margin-top: 18px; }}
  .examples summary {{ cursor: pointer; color: #8ab4ff; font-weight: 600; }}
  .ex-row {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }}
  .ex-row button {{
    font-weight: 400; font-size: 0.78rem; padding: 6px 10px; border-radius: 6px;
    background: #2a2a2a; border: 1px solid #444;
  }}
{review_nav_css()}
</style>
</head>
<body>
  {render_review_nav("rag")}
  <h1>Consulta con citas — RAG</h1>
  <p class="meta">Respuesta generada con <b>OpenRouter</b> sobre evidencia del corpus indexado.
     Para solo fragmentos, usa <a href="/search.html">búsqueda híbrida</a>.</p>
  {intro}
  <div class="bar">
    <input id="q" type="search" placeholder="Pregunta completa: definición, criterio, procedimiento, checklist…"/>
    <button id="ask" class="primary">Preguntar</button>
    <button id="clear" class="ghost" type="button" title="Limpiar">Limpiar</button>
  </div>
  <div id="question" class="question-box" hidden>
    <span class="label">Consulta</span>
    <span id="question-text"></span>
  </div>
  <div id="status"></div>
  <div id="conflict-banner" class="conflict-banner" hidden></div>
  <ul id="conflicts" class="conflict-list" hidden></ul>
  <div class="layout">
    <section class="panel answer-panel" aria-live="polite">
      <div class="panel-head">Respuesta</div>
      <div class="panel-body">
        <div id="answer" class="answer-empty">Escribe una pregunta y pulsa <b>Preguntar</b>, o elige un ejemplo abajo.</div>
      </div>
    </section>
    <aside class="panel refs-panel">
      <div class="panel-head">Referencias citadas</div>
      <div class="panel-body">
        <ol id="references" class="refs-list"></ol>
        <p id="refs-empty" class="answer-empty">Las fuentes citadas [1][2]… aparecerán aquí.</p>
      </div>
    </aside>
  </div>
  <div class="evidence-section">
    <details class="evidence" id="evidence-wrap" open>
      <summary id="evidence-summary">Fragmentos de evidencia</summary>
      <div class="evidence-inner" id="evidence"></div>
    </details>
  </div>
  <details class="examples">
    <summary>Ejemplos de consulta</summary>
    <div class="ex-row">
      <button type="button" data-q="SGP-07MYC-GUIGS-00001 Rev 6 alcance mantenibilidad confiabilidad proyectos">GUIGS Rev 6</button>
      <button type="button" data-q="NCC-030 requisitos criticidad mantenibilidad confiabilidad">NCC-030 criticidad</button>
      <button type="button" data-q="Anexo C checklist accesibilidad cumplimiento mantenibilidad GUIGS">Anexo C checklist</button>
      <button type="button" data-q="FMECA modos falla efectos criticidad sistema enfriamiento torre DCH">FMECA enfriamiento</button>
      <button type="button" data-q="SGPD-07MYC-FRMGS-0036 RCM tareas mantenimiento recomendadas">Plantilla RCM</button>
      <button type="button" data-q="¿Qué es la mantenibilidad y cómo se evalúa según GUIGS Rev 6?">Definición M&amp;C</button>
    </div>
  </details>
<script>
const q = document.getElementById('q');
const askBtn = document.getElementById('ask');
const clearBtn = document.getElementById('clear');
const statusEl = document.getElementById('status');
const answerEl = document.getElementById('answer');
const refsEl = document.getElementById('references');
const refsEmpty = document.getElementById('refs-empty');
const evidenceEl = document.getElementById('evidence');
const evidenceSummary = document.getElementById('evidence-summary');
const questionBox = document.getElementById('question');
const questionText = document.getElementById('question-text');
const conflictBannerEl = document.getElementById('conflict-banner');
const conflictsEl = document.getElementById('conflicts');
let lastAsk = null;

document.querySelectorAll('[data-q]').forEach(b => {{
  b.onclick = () => {{ q.value = b.dataset.q; runAsk(); }};
}});
askBtn.onclick = runAsk;
clearBtn.onclick = clearAll;
q.addEventListener('keydown', e => {{ if (e.key === 'Enter') runAsk(); }});

function esc(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

function apiError(res, fallback) {{
  if (res.status === 404) {{
    return 'API no disponible (404). Ejecuta: python -m mmi.tools.serve_local --port 8773';
  }}
  return fallback || ('HTTP ' + res.status);
}}

function setStatus(text, ok) {{
  statusEl.textContent = text;
  statusEl.className = ok ? 'ok' : '';
}}

function showError(err) {{
  const hint = location.protocol === 'file:'
    ? ' Abre http://127.0.0.1:8773/rag.html (no el archivo directo).'
    : '';
  setStatus('Error: ' + err.message + hint, false);
}}

function clearAll() {{
  q.value = '';
  lastAsk = null;
  questionBox.hidden = true;
  answerEl.innerHTML = 'Escribe una pregunta y pulsa <b>Preguntar</b>, o elige un ejemplo abajo.';
  answerEl.className = 'answer-empty';
  refsEl.innerHTML = '';
  refsEmpty.hidden = false;
  evidenceEl.innerHTML = '';
  evidenceSummary.textContent = 'Fragmentos de evidencia';
  conflictBannerEl.hidden = true;
  conflictBannerEl.textContent = '';
  conflictsEl.hidden = true;
  conflictsEl.innerHTML = '';
  setStatus('', false);
  history.replaceState(null, '', '/rag.html');
}}

function linkCites(s) {{
  return s.replace(/\\[(\\d+)\\]/g, '<a class="cite-link" href="#ref-$1">[$1]</a>');
}}

function renderAnswer(text) {{
  if (!text) return '<p class="answer-empty">Sin respuesta.</p>';
  const lines = esc(text).split('\\n');
  const parts = [];
  let inList = false;
  for (const line of lines) {{
    const h = line.match(/^## (.+)$/);
    if (h) {{
      if (inList) {{ parts.push('</ul>'); inList = false; }}
      parts.push('<h3>' + h[1] + '</h3>');
      continue;
    }}
    const li = line.match(/^- (.+)$/);
    if (li) {{
      if (!inList) {{ parts.push('<ul>'); inList = true; }}
      parts.push('<li>' + linkCites(li[1]) + '</li>');
      continue;
    }}
    if (inList) {{ parts.push('</ul>'); inList = false; }}
    if (line.trim()) parts.push('<p>' + linkCites(line) + '</p>');
  }}
  if (inList) parts.push('</ul>');
  return '<div class="answer-body">' + parts.join('') + '</div>';
}}

function renderReferences(refs) {{
  if (!refs.length) {{
    refsEl.innerHTML = '';
    refsEmpty.hidden = false;
    return;
  }}
  refsEmpty.hidden = true;
  refsEl.innerHTML = refs.map(r => `
    <li id="ref-${{r.index}}" class="cited">
      <span class="ref-num">[${{r.index}}]</span>
      <strong>${{esc(r.citation || r.titulo || 'Fuente')}}</strong>
      <div class="ref-meta">${{esc([r.tipo, r.version_label, r.section_path,
        r.page_start ? 'pág. ' + r.page_start + (r.page_end && r.page_end !== r.page_start ? '–' + r.page_end : '') : ''
      ].filter(Boolean).join(' · '))}}</div>
      ${{r.snippet ? '<div class="ref-snippet">“' + esc(r.snippet) + '…”</div>' : ''}}
    </li>`).join('');
}}

function renderHits(hits, citedSet) {{
  citedSet = citedSet || new Set();
  if (!hits.length) {{
    evidenceEl.innerHTML = '<p class="answer-empty">Sin fragmentos recuperados.</p>';
    evidenceSummary.textContent = 'Fragmentos de evidencia (0)';
    return;
  }}
  evidenceSummary.textContent = 'Fragmentos de evidencia (' + hits.length + ')';
  evidenceEl.innerHTML = hits.map((r, i) => {{
    const n = i + 1;
    const cited = citedSet.has(n);
    return `
      <div class="hit${{cited ? ' cited' : ''}}" id="evidence-${{n}}">
        <h3>${{n}}. ${{esc(r.citation || r.titulo || 'Resultado')}}${{cited ? ' <span class="badge">citada</span>' : ''}}</h3>
        <div>
          <span class="badge">${{esc(r.tipo||'')}}</span>
          <span class="badge ${{r.criticality_level==='seguridad'?'seg':''}}">${{esc(r.criticality_level||'')}}</span>
          <span class="badge">score ${{r.score}}</span>
        </div>
        <div class="snippet">${{esc(r.content||'')}}</div>
      </div>`;
  }}).join('');
}}

function renderConflicts(banner, conflictos) {{
  conflictos = conflictos || [];
  if (!banner || !banner.visible || !conflictos.length) {{
    conflictBannerEl.hidden = true;
    conflictBannerEl.textContent = '';
    conflictsEl.hidden = true;
    conflictsEl.innerHTML = '';
    return;
  }}
  const sev = banner.severity === 'warn' ? '' : 'info';
  conflictBannerEl.className = 'conflict-banner' + (sev ? ' ' + sev : '');
  conflictBannerEl.textContent = banner.message || ('Conflicto documental detectado (' + conflictos.length + ')');
  conflictBannerEl.hidden = false;
  conflictsEl.hidden = false;
  conflictsEl.innerHTML = conflictos.map(c => `
    <li class="${{c.severity === 'info' ? 'info' : ''}}">
      <div class="conflict-kind">${{esc(c.kind || 'conflicto')}}</div>
      ${{esc(c.text || '')}}
    </li>`).join('');
}}

document.addEventListener('click', e => {{
  const link = e.target.closest('a.cite-link');
  if (!link) return;
  e.preventDefault();
  const target = document.getElementById(link.getAttribute('href').slice(1));
  if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
}});

async function fetchAskDetails(section) {{
  const res = await fetch('/api/ask-details', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ ask_id: lastAsk.ask_id, section }}),
  }});
  if (!res.ok) {{
    const err = await res.json().catch(() => ({{}}));
    throw new Error(apiError(res, err.error));
  }}
  return res.json();
}}

async function runAsk() {{
  const query = q.value.trim();
  if (!query) return;
  askBtn.disabled = true;
  setStatus('Recuperando evidencia y generando respuesta…', false);
  answerEl.innerHTML = '<p class="answer-empty">Generando…</p>';
  answerEl.className = '';
  refsEl.innerHTML = '';
  refsEmpty.hidden = true;
  evidenceEl.innerHTML = '<p class="answer-empty">Cargando…</p>';
  conflictBannerEl.hidden = true;
  conflictsEl.hidden = true;
  questionBox.hidden = false;
  questionText.textContent = query;
  history.replaceState(null, '', '/rag.html?q=' + encodeURIComponent(query));
  try {{
    const res = await fetch('/api/ask', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ query, limit: 8 }}),
    }});
    if (!res.ok) {{
      const err = await res.json().catch(() => ({{}}));
      throw new Error(apiError(res, err.error));
    }}
    const data = await res.json();
    lastAsk = {{ ask_id: data.ask_id, cited_indices: data.cited_indices || [] }};
    answerEl.innerHTML = renderAnswer(data.answer || '');
    answerEl.className = '';
    renderConflicts(data.conflict_banner, data.conflictos);
    setStatus(
      data.cited_count + ' referencias · ' + data.evidence_count + ' evidencias · '
      + (data.elapsed_ms || '?') + ' ms · ' + (data.model || ''),
      true
    );
    const citedSet = new Set(data.cited_indices || []);
    const [refsData, evData] = await Promise.all([
      fetchAskDetails('references'),
      fetchAskDetails('evidence'),
    ]);
    renderReferences(refsData.references || []);
    renderHits(evData.results || [], citedSet);
  }} catch (err) {{
    showError(err);
    answerEl.innerHTML = '<p class="answer-empty">No se pudo generar la respuesta.</p>';
    evidenceEl.innerHTML = '';
  }} finally {{
    askBtn.disabled = false;
  }}
}}

(function boot() {{
  const params = new URLSearchParams(location.search);
  const initial = params.get('q');
  if (initial) {{
    q.value = initial;
    runAsk();
  }} else {{
    q.focus();
  }}
}})();
</script>
</body>
</html>"""
