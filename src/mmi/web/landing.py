"""Landing page — catalogo de paginas HTML servidas desde out/."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from mmi.analysis.review_shell import review_nav_css

PageSpec = dict[str, str]

SectionSpec = dict[str, Any]

# Catalogo curado; el generador marca disponibilidad segun archivos en out/.
LANDING_SECTIONS: tuple[SectionSpec, ...] = (
    {
        "id": "producto",
        "title": "Producto y demo",
        "description": "Experiencia comercial y flujo de diagnostico conectado al motor.",
        "pages": (
            {"file": "app.html", "title": "App MMI", "desc": "Landing comercial + demo diagnostico (Overview → Loading → Final)."},
        ),
    },
    {
        "id": "ingesta",
        "title": "Ingesta y revision",
        "description": "Estado del corpus, resultados de pipeline y herramientas de revision humana.",
        "pages": (
            {"file": "ingestion-results.html", "title": "Resultados ingesta", "desc": "KPIs, tokens, OCR, cobertura y detalle por documento."},
            {"file": "review.html", "title": "Hub de revision", "desc": "Panel central de Fase 0, filtros y acciones sobre el manifest."},
            {"file": "data-quality.html", "title": "Calidad de datos", "desc": "Informe de calidad y cobertura del corpus analizado."},
            {"file": "corpus-picker.html", "title": "Selector de corpus", "desc": "Elegir y configurar la raiz del corpus local."},
            {"file": "source-review.html", "title": "Enlace nube", "desc": "Fuente remota (SharePoint / URL) para sincronizacion."},
        ),
    },
    {
        "id": "consulta",
        "title": "Consulta y motor",
        "description": "Busqueda hibrida, RAG, mapa de activos y analisis MMI.",
        "pages": (
            {"file": "search.html", "title": "Busqueda hibrida", "desc": "Fragmentos del indice con filtros por tipo y carpeta."},
            {"file": "rag.html", "title": "Consulta RAG", "desc": "Preguntas en lenguaje natural con citas y contexto."},
            {"file": "motor.html", "title": "Motor MMI", "desc": "Analisis de activo: sintomas, hipotesis, evidencia y plan."},
            {"file": "mapa.html", "title": "Mapa de activos", "desc": "Grafo de equipos, tags y navegacion hacia el motor."},
        ),
    },
    {
        "id": "validacion",
        "title": "Validacion y calidad",
        "description": "Golden set, smoke tests, catalogo EAM y pruebas de carga.",
        "pages": (
            {"file": "rag-validation.html", "title": "Validacion RAG", "desc": "Bateria de preguntas contra el indice activo."},
            {"file": "catalog-validation.html", "title": "Catalogo EAM", "desc": "Cruce de tags y equipos con el manifest."},
            {"file": "golden-set-eval.html", "title": "Golden set", "desc": "Metricas MRR y recall sobre consultas de referencia."},
            {"file": "load-test-report.html", "title": "Prueba de carga", "desc": "Latencias y throughput de consultas RAG."},
        ),
    },
    {
        "id": "legacy",
        "title": "Alias y vistas auxiliares",
        "description": "Paginas de compatibilidad o generadas en subcarpetas del manifest.",
        "pages": (
            {"file": "analysis-status.html", "title": "Estado analisis (alias)", "desc": "Redireccion o vista legacy de analysis-status."},
            {"file": "ingestion-status.html", "title": "Estado ingesta (alias)", "desc": "Vista legacy del progreso de ingesta."},
        ),
    },
)


def _discover_html(out_dir: Path) -> set[str]:
    if not out_dir.is_dir():
        return set()
    return {p.name for p in out_dir.glob("*.html")}


def _extra_pages(out_dir: Path, catalog_files: set[str]) -> list[PageSpec]:
    extras: list[PageSpec] = []
    for name in sorted(_discover_html(out_dir)):
        if name in catalog_files or name == "index.html":
            continue
        extras.append(
            {
                "file": name,
                "title": name.replace(".html", "").replace("-", " ").title(),
                "desc": "Pagina detectada automaticamente en out/.",
            }
        )
    return extras


def build_landing_catalog(out_dir: Path) -> dict[str, Any]:
    out_dir = Path(out_dir)
    available = _discover_html(out_dir)
    catalog_files: set[str] = set()
    sections: list[dict[str, Any]] = []

    for section in LANDING_SECTIONS:
        pages: list[dict[str, Any]] = []
        for page in section["pages"]:
            file_name = page["file"]
            catalog_files.add(file_name)
            pages.append({**page, "available": file_name in available})
        sections.append(
            {
                "id": section["id"],
                "title": section["title"],
                "description": section["description"],
                "pages": pages,
            }
        )

    extra = _extra_pages(out_dir, catalog_files)
    if extra:
        sections.append(
            {
                "id": "otros",
                "title": "Otros HTML en out/",
                "description": "Archivos no listados en el catalogo principal.",
                "pages": [{**p, "available": True} for p in extra],
            }
        )

    listed = sum(len(s["pages"]) for s in sections)
    ready = sum(1 for s in sections for p in s["pages"] if p.get("available"))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "out_dir": str(out_dir.resolve()),
        "summary": {"sections": len(sections), "pages_listed": listed, "pages_available": ready},
        "sections": sections,
    }


def render_landing_html(catalog: dict[str, Any]) -> str:
    from mmi.analysis.review_shell import render_review_nav

    summary = catalog.get("summary") or {}
    sections_html: list[str] = []

    for section in catalog.get("sections") or []:
        cards: list[str] = []
        for page in section.get("pages") or []:
            file_name = page.get("file", "")
            available = bool(page.get("available"))
            status_cls = "ok" if available else "missing"
            status_label = "Disponible" if available else "No generada"
            href = escape(file_name) if available else "#"
            card_cls = "page-card" if available else "page-card missing"
            disabled = ' aria-disabled="true"' if not available else ""
            cards.append(
                f'<a class="{card_cls}" href="{href}"{disabled}>'
                f'<span class="pc-status {status_cls}">{escape(status_label)}</span>'
                f'<h3>{escape(page.get("title") or file_name)}</h3>'
                f'<p>{escape(page.get("desc") or "")}</p>'
                f'<code>{escape(file_name)}</code>'
                f"</a>"
            )
        sections_html.append(
            f'<section class="landing-section" id="{escape(section.get("id", ""))}">'
            f"<h2>{escape(section.get('title', ''))}</h2>"
            f'<p class="section-desc">{escape(section.get("description") or "")}</p>'
            f'<div class="page-grid">{"".join(cards)}</div>'
            f"</section>"
        )

    return f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MMI — Portal local</title>
<style>
{review_nav_css()}
:root {{
  --bg: #0f1419; --surface: #161b22; --border: #30363d; --text: #e6edf3;
  --muted: #8b949e; --accent: #58a6ff; --ok: #3fb950; --warn: #d29922;
}}
* {{ box-sizing: border-box; }}
body {{ font-family: "Segoe UI", system-ui, sans-serif; margin: 0; padding: 20px 24px 56px;
  background: var(--bg); color: var(--text); }}
.hero {{ max-width: 1100px; margin: 0 auto 28px; }}
.hero h1 {{ font-size: 1.75rem; margin: 0 0 8px; }}
.hero p {{ color: var(--muted); margin: 0; line-height: 1.55; max-width: 720px; }}
.hero-stats {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
.stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 14px; min-width: 120px; }}
.stat span {{ display: block; font-size: 0.72rem; color: var(--muted); text-transform: uppercase; }}
.stat b {{ font-size: 1.25rem; }}
.toolbar {{ max-width: 1100px; margin: 0 auto 20px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
.toolbar input {{ flex: 1 1 240px; padding: 10px 12px; border-radius: 8px; border: 1px solid var(--border);
  background: #0d1117; color: var(--text); }}
.toolbar .hint {{ font-size: 0.8rem; color: var(--muted); }}
.landing-wrap {{ max-width: 1100px; margin: 0 auto; }}
.landing-section {{ margin-bottom: 32px; }}
.landing-section h2 {{ font-size: 1.1rem; margin: 0 0 6px; color: #b8c5d6; }}
.section-desc {{ color: var(--muted); font-size: 0.88rem; margin: 0 0 14px; }}
.page-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }}
.page-card {{ display: block; background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 16px; text-decoration: none; color: inherit; transition: border-color 0.15s, transform 0.1s; }}
.page-card:hover {{ border-color: var(--accent); transform: translateY(-1px); }}
.page-card.missing {{ opacity: 0.55; pointer-events: none; }}
.page-card h3 {{ margin: 8px 0 6px; font-size: 1rem; }}
.page-card p {{ margin: 0 0 10px; font-size: 0.84rem; color: var(--muted); line-height: 1.45; }}
.page-card code {{ font-size: 0.75rem; color: #79c0ff; background: #0d1117; padding: 2px 6px; border-radius: 4px; }}
.pc-status {{ font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }}
.pc-status.ok {{ color: var(--ok); }}
.pc-status.missing {{ color: var(--warn); }}
.footer {{ max-width: 1100px; margin: 36px auto 0; font-size: 0.8rem; color: var(--muted); }}
.footer a {{ color: var(--accent); }}
.hidden {{ display: none !important; }}
</style></head><body>
{render_review_nav("home", depth=0)}

<div class="hero">
  <h1>MMI — Portal local</h1>
  <p>Indice de todas las paginas HTML del proyecto. Sirvelas con
    <code>python -m mmi.tools.serve_local --port 8773</code> (no abras <code>file://</code>).</p>
  <div class="hero-stats">
    <div class="stat"><span>Secciones</span><b>{summary.get('sections', 0)}</b></div>
    <div class="stat"><span>Paginas listadas</span><b>{summary.get('pages_listed', 0)}</b></div>
    <div class="stat"><span>Disponibles</span><b>{summary.get('pages_available', 0)}</b></div>
  </div>
</div>

<div class="toolbar">
  <input id="q" type="search" placeholder="Filtrar por titulo, archivo o descripcion…" autofocus/>
  <span class="hint">Generado: {escape(catalog.get('generated_at', ''))}</span>
</div>

<div class="landing-wrap" id="sections">
{"".join(sections_html)}
</div>

<div class="footer">
  <p>Salida: <code>{escape(catalog.get('out_dir', ''))}</code> ·
  APIs: <a href="api/motor/health">motor/health</a>,
  <a href="api/graph/health">graph/health</a>,
  <a href="api/ingestion-results">ingestion-results</a></p>
</div>

<script>
(function() {{
  const q = document.getElementById('q');
  const sections = document.querySelectorAll('.landing-section');
  function filter() {{
    const needle = (q.value || '').toLowerCase().trim();
    sections.forEach(section => {{
      let visible = 0;
      section.querySelectorAll('.page-card').forEach(card => {{
        const blob = card.textContent.toLowerCase();
        const show = !needle || blob.includes(needle);
        card.classList.toggle('hidden', !show);
        if (show) visible++;
      }});
      section.classList.toggle('hidden', visible === 0);
    }});
  }}
  q.addEventListener('input', filter);
}})();
</script>
</body></html>"""


def write_landing_page(out_dir: Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    catalog = build_landing_catalog(out_dir)
    html_path = out_dir / "index.html"
    json_path = out_dir / "landing-catalog.json"
    html_path.write_text(render_landing_html(catalog), encoding="utf-8")
    json_path.write_text(
        __import__("json").dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return html_path, json_path
