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


def render_search_html(out_dir: Path | None = None) -> str:
    from mmi.analysis.review_shell import render_review_nav, review_nav_css
    from mmi.search.examples import render_search_examples_html

    examples_html = render_search_examples_html(out_dir=out_dir)
    prefix = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>MMI — Búsqueda con citas</title>
<style>
  :root {{ font-family: Segoe UI, system-ui, sans-serif; color: #e8e8e8; background: #1a1a1a; }}
  body {{ margin: 0; padding: 24px; max-width: 960px; }}
  h1 {{ font-size: 1.3rem; margin: 0 0 8px; }}
  .meta {{ color: #9a9a9a; margin-bottom: 16px; font-size: 0.9rem; }}
  .bar {{ display: flex; gap: 8px; margin-bottom: 16px; }}
  input[type=search] {{ flex: 1; padding: 10px 12px; border-radius: 8px; border: 1px solid #444;
    background: #111; color: #eee; font-size: 1rem; }}
  button {{ padding: 10px 16px; border-radius: 8px; border: none; background: #2a2a2a;
    color: #fff; font-weight: 600; cursor: pointer; border: 1px solid #444; }}
  button.primary {{ background: #2b5cff; border-color: #2b5cff; }}
  button:hover {{ filter: brightness(1.1); }}
  .answer-box {{ border: 1px solid #2d4a2d; border-radius: 8px; padding: 16px; margin-bottom: 16px;
    background: #1a241a; line-height: 1.55; }}
  .answer-box h2 {{ margin: 0 0 8px; font-size: 1rem; color: #8fddb0; }}
  .answer-body h3 {{ margin: 14px 0 8px; font-size: 0.95rem; color: #b8e6c8; }}
  .answer-body p {{ margin: 0 0 10px; color: #ddd; }}
  .answer-body ul {{ margin: 0 0 10px; padding-left: 20px; color: #ddd; }}
  .answer-body li {{ margin-bottom: 6px; }}
  .refs-box {{ border: none; padding: 0; margin: 0; background: transparent; }}
  details.optional-panel {{ border: 1px solid #2a3a5a; border-radius: 8px; padding: 10px 14px;
    margin-bottom: 14px; background: #1a1f2e; }}
  details.optional-panel.evidence {{ border-color: #333; background: #1c1c1c; }}
  details.optional-panel > summary {{ cursor: pointer; font-weight: 600; font-size: 0.92rem;
    color: #8ab4ff; list-style: none; }}
  details.optional-panel.evidence > summary {{ color: #b0b0b0; }}
  details.optional-panel > summary::-webkit-details-marker {{ display: none; }}
  details.optional-panel[open] > summary {{ margin-bottom: 10px; }}
  details.optional-panel .refs-list {{ margin-top: 4px; }}
  .lazy-status {{ margin: 0; color: #8a8a8a; font-size: 0.84rem; font-style: italic; }}
  .refs-list {{ margin: 0; padding-left: 0; list-style: none; }}
  .refs-list li {{ margin-bottom: 10px; padding: 8px 10px; border-radius: 6px; background: #151a24;
    border: 1px solid #2a3344; font-size: 0.88rem; line-height: 1.4; }}
  .refs-list li.cited {{ border-color: #3d5a8a; }}
  .ref-num {{ display: inline-block; min-width: 2rem; font-weight: 700; color: #8ab4ff; }}
  .ref-meta {{ color: #8a9ab0; font-size: 0.8rem; margin-top: 4px; }}
  .ref-snippet {{ color: #9aa8bc; font-size: 0.82rem; margin-top: 6px; font-style: italic; }}
  .cite-link {{ color: #8ab4ff; text-decoration: none; font-weight: 600; }}
  .cite-link:hover {{ text-decoration: underline; }}
  .hit.cited {{ border-color: #3d5a8a; }}
  details.help {{ border: 1px solid #333; border-radius: 12px; padding: 14px 16px; margin-bottom: 16px;
    background: #1c1c1c; }}
  details.help > summary {{ cursor: pointer; font-weight: 600; color: #d4e4ff; font-size: 1rem; }}
  .help-intro {{ margin: 10px 0 12px; color: #9a9a9a; font-size: 0.86rem; line-height: 1.45; }}
  .corpus-stats {{ color: #b8c8e0; font-size: 0.88rem; margin: 0 0 14px; line-height: 1.5;
    padding: 10px 14px; border-radius: 8px; background: #1a2438; border: 1px solid #2a3a5a; }}
  details.corpus-examples > summary {{ color: #8fddb0; }}
  details.search-tips {{ margin-top: 10px; }}
  .help-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(272px, 1fr)); gap: 12px; }}
  .help-card {{ border: 1px solid #2f2f2f; border-radius: 10px; padding: 14px 14px 12px;
    background: linear-gradient(160deg, #222 0%, #1a1a1a 100%); transition: border-color .15s, box-shadow .15s; }}
  .help-card:hover {{ border-color: #4a6288; box-shadow: 0 4px 14px rgba(0,0,0,.25); }}
  .help-card-head {{ display: flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; }}
  .help-card-icon {{ width: 34px; height: 34px; border-radius: 8px; display: flex; align-items: center;
    justify-content: center; font-size: 0.72rem; font-weight: 700; flex-shrink: 0; background: #2a3344; color: #8ab4ff; }}
  .help-card h3 {{ margin: 0; font-size: 0.9rem; color: #e8eef8; line-height: 1.3; }}
  .help-card-tag {{ display: block; margin-top: 3px; font-size: 0.72rem; color: #7a8aa0; }}
  .help-card ul {{ margin: 0 0 10px; padding-left: 16px; color: #aaa; font-size: 0.82rem; line-height: 1.45; }}
  .help-card li {{ margin-bottom: 4px; }}
  .help-card code {{ background: #111; padding: 1px 5px; border-radius: 4px; font-size: 0.78rem; }}
  .help-card.wide {{ grid-column: 1 / -1; }}
  .ex-btns {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }}
  .ex-btns button {{ background: #2a2a2a; border: 1px solid #444; font-weight: 400; font-size: 0.78rem;
    padding: 5px 9px; border-radius: 6px; color: #eee; cursor: pointer; }}
  .ex-btns button:hover {{ filter: brightness(1.12); border-color: #5a7ab8; }}
  .ex-btns button.search-only {{ border-color: #3a4a3a; color: #b8ddb0; }}
  .hit {{ border: 1px solid #333; border-radius: 8px; padding: 14px; margin-bottom: 12px;
    background: #202020; }}
  .hit h3 {{ margin: 0 0 6px; font-size: 0.95rem; color: #d4e4ff; }}
  .badge {{ font-size: 0.72rem; padding: 2px 7px; border-radius: 999px; background: #2a2a2a;
    color: #aaa; margin-right: 6px; }}
  .badge.seg {{ background: #3d321a; color: #e6c07b; }}
  .cite {{ color: #8ab4ff; font-size: 0.85rem; margin-bottom: 8px; }}
  .snippet {{ color: #ccc; font-size: 0.88rem; line-height: 1.45; white-space: pre-wrap; }}
  #status {{ color: #9a9a9a; margin-top: 8px; }}
  a {{ color: #8ab4ff; }}
{review_nav_css()}
</style>
</head>
<body>
  {render_review_nav("search")}
"""
    body_start = """
  <h1>Búsqueda híbrida — memoria técnica NCC30</h1>
  <p class="meta">Búsqueda de fragmentos: Qdrant + Supabase ·
     Respuestas con citas en <a href="rag.html">Consulta RAG</a> (OpenRouter)</p>
  <div class="bar">
    <input id="q" type="search" placeholder="Términos, códigos de documento, checklist, FMECA, matriz MRI…"/>
    <button id="go" class="primary">Buscar</button>
    <button id="ask" type="button">Consulta RAG →</button>
  </div>

"""
    body_rest = """
  <div id="status"></div>
  <div id="results"></div>
<script>
const q = document.getElementById('q');
const go = document.getElementById('go');
const askBtn = document.getElementById('ask');
const status = document.getElementById('status');
const results = document.getElementById('results');
let lastSearch = null;

function goRag(query) {
  const text = (query != null ? query : q.value).trim();
  if (!text) return;
  location.href = 'rag.html?q=' + encodeURIComponent(text);
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
  results.innerHTML = '';
  lastSearch = null;
  try {
    const res = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 8 }),
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

function mountSearchResultsPlaceholder(count) {
  if (!count) { results.innerHTML = ''; return; }
  results.innerHTML = '<details class="optional-panel evidence" id="evidence-panel" open>'
    + '<summary>Resultados (' + count + ')</summary>'
    + '<p class="lazy-status">Cargando…</p></details>';
  loadSearchResults();
}

async function loadSearchResults() {
  if (!lastSearch || lastSearch.loaded) return;
  lastSearch.loaded = true;
  renderHits(lastSearch.results);
}

function renderHits(hits) {
  if (!hits.length) { results.innerHTML = ''; return; }
  const inner = hits.map((r, i) => {
    const n = i + 1;
    return `
      <div class="hit" id="evidence-${n}">
        <h3>${n}. ${esc(r.citation || r.titulo || 'Resultado')}</h3>
        <div>
          <span class="badge">${esc(r.tipo||'')}</span>
          <span class="badge ${r.criticality_level==='seguridad'?'seg':''}">${esc(r.criticality_level||'')}</span>
          <span class="badge">score ${r.score}</span>
        </div>
        <p class="cite">${esc(r.citation||'')}</p>
        <div class="snippet">${esc(r.content||'')}</div>
        <p class="meta" style="margin-top:10px"><a href="rag.html?q=${encodeURIComponent(q.value.trim())}">Preguntar sobre esto en Consulta RAG →</a></p>
      </div>`;
  }).join('');
  results.innerHTML = '<details class="optional-panel evidence" id="evidence-panel" open>'
    + '<summary>Resultados (' + hits.length + ')</summary>' + inner + '</details>';
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
</script>
</body>
</html>"""
    return prefix + body_start + examples_html + body_rest


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
        from mmi.search.rag_page import render_rag_html

        out_dir = args.write_html.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        args.write_html.write_text(render_search_html(out_dir), encoding="utf-8")
        rag_path = out_dir / "rag.html"
        rag_path.write_text(render_rag_html(out_dir), encoding="utf-8")
        print(f"HTML → {args.write_html.resolve()}")
        print(f"RAG  → {rag_path.resolve()}")
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
