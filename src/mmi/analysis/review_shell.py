"""Shell unificado de navegación y escritura HTML para revisión MMI."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

REVIEW_HUB = "review.html"
REVIEW_JSON = "analysis-status.json"
LEGACY_ALIASES = ("ingestion-status.html", "analysis-status.html")

_NAV_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("home", "index.html", "Inicio"),
    ("app", "app.html", "App MMI"),
    ("ingestion", "ingestion-results.html", "Ingesta"),
    ("hub", REVIEW_HUB, "Revisión"),
    ("search", "search.html", "Búsqueda"),
    ("rag", "rag.html", "Consulta RAG"),
    ("mapa", "mapa.html", "Mapa"),
    ("motor", "motor.html", "Motor MMI"),
    ("corpus", "corpus-picker.html", "Corpus"),
    ("cloud", "source-review.html", "Enlace nube"),
)

_VITRINA_NAV_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("home", "index.html", "Inicio"),
    ("pruebas", "pruebas.html", "Pruebas"),
    ("ejemplos", "ejemplos.html", "Ejemplos"),
    ("search", "search.html", "Búsqueda"),
    ("rag", "rag.html", "Consulta"),
)


def _nav_items() -> tuple[tuple[str, str, str], ...]:
    from mmi.web.deploy_mode import is_vitrina

    return _VITRINA_NAV_ITEMS if is_vitrina() else _NAV_ITEMS


def nav_href(page: str, *, depth: int = 0) -> str:
    if depth == 0:
        from mmi.web.deploy_mode import is_vitrina

        if is_vitrina():
            return f"/{page.lstrip('/')}"
    return f"{'../' * depth}{page}"


def review_nav_css() -> str:
    return """
  .review-nav {
    display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px;
    padding: 10px 14px; margin-bottom: 16px; border-radius: 8px;
    background: #202020; border: 1px solid #333; font-size: 0.85rem;
  }
  .review-nav .brand { font-weight: 600; color: #e8e8e8; margin-right: 8px; }
  .review-nav a {
    color: #8ab4ff; text-decoration: none; padding: 4px 8px; border-radius: 6px;
  }
  .review-nav a:hover { background: #2a2a2a; }
  .review-nav a.active { background: #2b5cff; color: #fff; }
  .review-nav .spacer { flex: 1 1 auto; }
  .review-data-links { margin-top: 12px; font-size: 0.82rem; }
  .review-data-links a { color: #8ab4ff; margin-right: 14px; }
  .phases-panel {
    margin: 0 0 18px; padding: 14px 16px; border-radius: 10px;
    background: #1a2233; border: 1px solid #2a3a55;
  }
  .phases-panel h2 { margin: 0 0 10px; font-size: 0.95rem; color: #b8c8e0; }
  .phases-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px;
  }
  .phase-card {
    padding: 10px 12px; border-radius: 8px; background: #141a24; border: 1px solid #2a3344;
    font-size: 0.82rem; line-height: 1.45;
  }
  .phase-card .phase-title { font-weight: 600; color: #e8e8e8; margin-bottom: 4px; }
  .phase-card .phase-status { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }
  .phase-card.done .phase-status { color: #8fddb0; }
  .phase-card.progress .phase-status { color: #f0d080; }
  .phase-card.pending .phase-status { color: #9a9a9a; }
  .phase-card ul { margin: 0; padding-left: 16px; color: #aab4c8; }
  .phase-card li { margin-bottom: 2px; }
"""


def render_review_nav(active: str = "hub", *, depth: int = 0) -> str:
    from mmi.web.deploy_mode import is_vitrina

    parts = ['<nav class="review-nav" aria-label="Revisión MMI">']
    parts.append(f'<span class="brand"><a href="{escape(nav_href("index.html", depth=depth))}" style="color:inherit;text-decoration:none">MMI</a></span>')
    for key, page, label in _nav_items():
        cls = ' class="active"' if key == active else ""
        parts.append(f'<a href="{escape(nav_href(page, depth=depth))}"{cls}>{escape(label)}</a>')
    if not is_vitrina():
        parts.append('<span class="spacer"></span>')
        parts.append(
            f'<a href="{escape(nav_href("rag-validation.html", depth=depth))}">Validación RAG</a>'
        )
        parts.append(
            f'<a href="{escape(nav_href("catalog-validation.html", depth=depth))}">Catálogo EAM</a>'
        )
        parts.append(
            f'<a href="{escape(nav_href("load-test-report.html", depth=depth))}">Carga</a>'
        )
    parts.append("</nav>")
    return "".join(parts)


def render_review_data_links(*, depth: int = 0) -> str:
    links = (
        ("catalog-validation.json", "Catálogo EAM"),
        ("rag-validation.json", "Validación RAG"),
        ("data-quality.html", "Análisis datos"),
        ("ingestion-results.html", "Ingesta"),
        ("index-corpus-summary.json", "Indexación"),
        ("ingestion-registry.json", "Jobs"),
        ("process-manifest.json", "Manifest"),
        (REVIEW_JSON, "Estado JSON"),
        ("version-detect-summary.json", "Identidad"),
    )
    items = "".join(
        f'<a href="{escape(nav_href(href, depth=depth))}">{escape(label)}</a>'
        for href, label in links
    )
    return f'<p class="review-data-links">{items}</p>'


def render_phases_panel(*, depth: int = 0) -> str:
    """Roadmap de fases visible en review.html (actualizar al cerrar bloques)."""
    eval_link = nav_href("golden-set-eval.html", depth=depth)
    ocr_link = nav_href("plan-scan.json", depth=depth)
    cards = [
        (
            "done",
            "Fase 0 — Extracción",
            "Cerrada MVP",
            [
                "PDF · Excel · PPTX · DOCX",
                "Dashboard + revisión por documento",
                "ODS1: 1513 pass",
            ],
        ),
        (
            "done",
            "Fase 1 — Indexación",
            "MVP activo",
            [
                "Qdrant + Supabase",
                "~365 docs · 57k chunks",
                "logical_key + duplicados",
            ],
        ),
        (
            "done",
            "Fase 2 — Búsqueda y RAG",
            "Operativo",
            [
                "Híbrido dense + BM25",
                "rag.html + citas OpenRouter",
                "C1 reranker · C2 conflictos · C3 golden set",
            ],
        ),
        (
            "progress",
            "Fase C — OCR y calidad",
            "En curso",
            [
                "C4 núcleo + Azure + plan_detect ✅",
                "Falta: indexar planos INF TEC",
                "Falta: PPTX visual · ocr_* en PG",
            ],
        ),
        (
            "done",
            "Motor MMI",
            "M1–M6 cerrado",
            [
                "motor.html · /api/motor/analyze",
                "Hechos · hipótesis · EAM",
                "Export checklist + discrepancias",
            ],
        ),
        (
            "pending",
            "Fase 3 — Producto",
            "Pendiente",
            [
                "Auth multi-tenant",
                "Despliegue cloud",
                "C5 cola async (opcional)",
            ],
        ),
    ]
    parts = [
        '<section class="phases-panel" aria-label="Fases del proyecto">',
        "<h2>Fases del proyecto</h2>",
        '<div class="phases-grid">',
    ]
    for state, title, status, bullets in cards:
        lis = "".join(f"<li>{escape(b)}</li>" for b in bullets)
        parts.append(
            f'<div class="phase-card {state}">'
            f'<div class="phase-title">{escape(title)}</div>'
            f'<div class="phase-status">{escape(status)}</div>'
            f"<ul>{lis}</ul></div>"
        )
    parts.append("</div>")
    parts.append(
        f'<p class="review-data-links" style="margin-top:10px">'
        f'<a href="{escape(eval_link)}">Golden set eval</a> · '
        f'<a href="{escape(ocr_link)}">Scan planos (JSON)</a></p>'
    )
    parts.append("</section>")
    return "".join(parts)


def render_redirect_html(target: str, *, title: str = "Redirigiendo…") -> str:
    href = escape(target)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta http-equiv="refresh" content="0; url={href}"/>
<title>{escape(title)}</title>
<script>location.replace("{href}");</script>
</head>
<body><p><a href="{href}">Ir a {href}</a></p></body>
</html>"""


def write_review_dashboard(out_dir: Path, payload: dict[str, Any]) -> Path:
    """Escribe review.html (canónico) + aliases redirect + JSON de estado."""
    from mmi.analysis.status import render_dashboard

    out_dir.mkdir(parents=True, exist_ok=True)
    dashboard = render_dashboard(payload)
    hub = out_dir / REVIEW_HUB
    hub.write_text(dashboard, encoding="utf-8")
    redirect = render_redirect_html(REVIEW_HUB, title="Revisión MMI")
    for alias in LEGACY_ALIASES:
        (out_dir / alias).write_text(redirect, encoding="utf-8")
    (out_dir / REVIEW_JSON).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return hub
