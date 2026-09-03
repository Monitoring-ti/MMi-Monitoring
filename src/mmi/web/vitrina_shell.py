"""Shell UI Monitoring (Tailwind) para paginas vitrina MMI."""

from __future__ import annotations

from html import escape
from typing import Any

# Logos locales: reemplazar SVG en public/ (se copian a out/ al generar vitrina).
LOGO_SIDEBAR = "/monitoring-logo-horizontal.svg"
LOGO_HEADER = "/monitoring-logo-horizontal.svg"
VITRINA_CSS = "/vitrina.css"
FOOTER_CREDIT = "Desarrollado por P.H.R. para Monitoring · sep 26 · v0.1"

DEFAULT_DOCUMENT_TITLE = "MMI | Análisis M&C - Sistema de Enfriamiento DCH"
DEFAULT_META_DESCRIPTION = (
    "Vitrina de ingesta MMI: análisis documental de mantenibilidad y confiabilidad "
    "(M&C) del sistema de enfriamiento DCH. Resultados de pruebas y consultas al corpus indexado."
)

NAV_ITEMS: tuple[tuple[str, str, str, str], ...] = (
    ("home", "index.html", "dashboard", "Inicio"),
    ("pruebas", "pruebas.html", "science", "Pruebas"),
    ("ejemplos", "ejemplos.html", "menu_book", "Ejemplos"),
    ("search", "search.html", "search", "Búsqueda"),
    ("rag", "rag.html", "psychology", "Consulta RAG"),
)


def _href(page: str) -> str:
    return f"/{page.lstrip('/')}"


def _nav_link(key: str, page: str, icon: str, label: str, active: str) -> str:
    is_active = key == active
    if is_active:
        cls = (
            "flex items-center gap-stack-md px-margin-mobile py-stack-md "
            "bg-primary-container text-on-primary-container transition-colors"
        )
    else:
        cls = (
            "flex items-center gap-stack-md px-margin-mobile py-stack-md "
            "text-primary-fixed-dim hover:bg-primary-container hover:text-on-primary-container transition-all"
        )
    return (
        f'<li><a href="{_href(page)}" class="{cls}">'
        f'<span class="material-symbols-outlined" aria-hidden="true">{escape(icon)}</span>'
        f'<span class="text-body-md font-medium">{escape(label)}</span></a></li>'
    )


def _mobile_nav(key: str, page: str, icon: str, label: str, active: str) -> str:
    is_active = key == active
    if is_active:
        wrap = "flex flex-col items-center justify-center bg-secondary-container text-on-secondary-container rounded-full px-4 py-1"
    else:
        wrap = "flex flex-col items-center justify-center text-on-surface-variant"
    return (
        f'<a href="{_href(page)}" class="{wrap}" aria-label="{escape(label)}">'
        f'<span class="material-symbols-outlined" aria-hidden="true">{escape(icon)}</span>'
        f'<span class="text-label-sm font-semibold">{escape(label)}</span></a>'
    )


def metric_card(
    *,
    icon: str,
    badge: str,
    title: str,
    value: str,
    subtitle: str,
    icon_bg: str = "bg-primary-fixed",
    icon_color: str = "text-on-primary-fixed",
    value_color: str = "text-primary",
    progress_pct: int | None = None,
    explanation: str = "",
) -> str:
    bar = ""
    if progress_pct is not None:
        bar = f"""
<div class="w-full bg-surface-container h-2 rounded-full overflow-hidden mt-base">
  <div class="bg-primary h-full rounded-full" style="width:{int(progress_pct)}%"></div>
</div>"""
    explain = ""
    if explanation:
        explain = f"""
<details class="metric-explain group mt-stack-md border-t border-outline/10 pt-stack-sm">
  <summary class="list-none cursor-pointer flex items-center justify-between gap-stack-sm text-label-sm font-semibold text-primary select-none hover:opacity-80 transition-opacity">
    <span class="inline-flex items-center gap-base">
      <span class="material-symbols-outlined text-outline" style="font-size:18px" aria-hidden="true">info</span>
      ¿Qué significa?
    </span>
    <span class="material-symbols-outlined text-outline group-open:rotate-180 transition-transform" style="font-size:18px" aria-hidden="true">expand_more</span>
  </summary>
  <p class="mt-stack-sm text-body-md text-on-surface-variant leading-relaxed">{escape(explanation)}</p>
</details>"""
    return f"""
<div class="bg-surface-container-lowest p-stack-lg rounded-lg border border-outline/20 shadow-sm hover:shadow-md transition-shadow">
  <div class="flex justify-between items-start mb-stack-md">
    <div class="p-stack-sm {icon_bg} rounded-xl {icon_color}" aria-hidden="true">
      <span class="material-symbols-outlined">{escape(icon)}</span>
    </div>
    <span class="text-on-surface-variant text-label-sm font-semibold uppercase">{escape(badge)}</span>
  </div>
  <div class="space-y-base">
    <h3 class="text-body-md text-on-surface-variant">{escape(title)}</h3>
    <div class="flex items-baseline gap-stack-sm flex-wrap">
      <span class="text-4xl font-bold leading-none {value_color}">{escape(value)}</span>
      <span class="text-label-sm font-semibold text-on-surface-variant">{escape(subtitle)}</span>
    </div>
    {bar}
    {explain}
  </div>
</div>"""


def render_shell(
    *,
    active: str,
    title: str,
    content: str,
    header_subtitle: str = "",
    corpus_lote: str = "ODS1",
    extra_head: str = "",
    footer_scripts: str = "",
    show_fab: bool = True,
    document_title: str | None = None,
    meta_description: str | None = None,
) -> str:
    nav = "".join(_nav_link(k, p, i, l, active) for k, p, i, l in NAV_ITEMS)
    mobile = "".join(_mobile_nav(k, p, i, l, active) for k, p, i, l in NAV_ITEMS)
    doc_title = document_title or f"{title} · {DEFAULT_DOCUMENT_TITLE}"
    description = meta_description or DEFAULT_META_DESCRIPTION
    fab_html = ""
    if show_fab:
        fab_html = f"""
  <a href="{_href('rag.html')}" class="fixed bottom-20 md:bottom-margin-desktop right-margin-mobile w-14 h-14 bg-secondary-container text-on-secondary-container rounded-full flex items-center justify-center shadow-lg hover:scale-105 transition-all z-40" title="Consulta RAG" aria-label="Abrir Consulta RAG">
    <span class="material-symbols-outlined" style="font-size:28px;font-variation-settings:'FILL' 1" aria-hidden="true">psychology</span>
  </a>"""
    subtitle_html = (
        f'<p class="text-body-md text-on-surface-variant mt-1">{escape(header_subtitle)}</p>'
        if header_subtitle
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="es" class="light">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta name="robots" content="noindex, nofollow, noarchive"/>
<meta name="description" content="{escape(description)}"/>
<title>{escape(doc_title)}</title>
<link rel="stylesheet" href="{VITRINA_CSS}"/>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=block" rel="stylesheet"/>
<style>
  details.metric-explain > summary {{-webkit-details-marker: none;}}
  details.metric-explain > summary::-webkit-details-marker {{ display: none; }}
</style>
{extra_head}
</head>
<body class="flex min-h-screen text-on-surface bg-background">
<aside class="hidden md:flex flex-col w-64 bg-primary text-on-primary fixed h-full z-50" aria-label="Navegación principal">
  <div class="p-stack-lg flex items-center gap-base">
    <div class="w-full bg-white rounded-lg p-stack-sm shadow-sm">
      <img src="{LOGO_SIDEBAR}" alt="Monitoring" class="w-full h-auto object-contain"/>
    </div>
  </div>
  <nav class="flex-1 mt-stack-md"><ul class="space-y-base">{nav}</ul></nav>
  <div class="p-margin-mobile mt-auto">
    <div class="bg-primary-container rounded-lg p-stack-md">
      <p class="text-label-sm text-on-primary-container opacity-80 uppercase mb-base tracking-wider">Proyecto</p>
      <div class="flex items-center justify-between gap-stack-sm">
        <span class="text-body-md font-bold">{escape(corpus_lote)}</span>
        <span class="material-symbols-outlined text-secondary-container" aria-hidden="true">verified</span>
      </div>
      <p class="text-label-sm text-on-primary-container opacity-70 mt-base">MMI · vitrina de ingesta</p>
    </div>
  </div>
</aside>
<main class="flex-1 md:ml-64 flex flex-col min-h-screen pb-20 md:pb-0">
  <header class="h-16 bg-surface flex justify-between items-center px-margin-mobile md:px-margin-desktop sticky top-0 z-40 shadow-sm border-b border-outline/10">
    <div class="flex items-center gap-stack-md min-w-0">
      <div class="bg-white rounded-lg p-1 shadow-sm shrink-0 md:hidden">
        <img src="{LOGO_HEADER}" alt="Monitoring" class="h-8 w-auto object-contain"/>
      </div>
      <div class="min-w-0">
        <h1 class="text-headline-md font-semibold text-primary truncate">{escape(title)}</h1>
        {subtitle_html}
      </div>
    </div>
    <div class="flex items-center gap-stack-md shrink-0">
      <a href="{_href('rag.html')}" class="hidden sm:flex items-center gap-base bg-surface-container-low px-stack-md py-2 rounded-full border border-outline/30 text-body-md text-on-surface-variant hover:border-primary transition-colors">
        <span class="material-symbols-outlined text-outline" style="font-size:20px" aria-hidden="true">search</span>
        <span>Consultar</span>
      </a>
      <a href="/api/motor/health" class="text-label-sm text-on-surface-variant hover:text-primary hidden lg:inline">API</a>
    </div>
  </header>
  <section class="p-margin-mobile md:p-margin-desktop space-y-gutter flex-1">
    {content}
  </section>
  <footer class="px-margin-mobile md:px-margin-desktop py-stack-md border-t border-outline/10 bg-surface-container-lowest">
    <p class="text-label-sm text-on-surface-variant text-center md:text-left">{escape(FOOTER_CREDIT)}</p>
  </footer>
{fab_html}
</main>
<nav class="md:hidden fixed bottom-0 w-full bg-surface flex justify-around items-center py-2 px-margin-mobile shadow-lg border-t border-outline/20 z-50" aria-label="Navegación móvil">{mobile}</nav>
{footer_scripts}
</body></html>"""
