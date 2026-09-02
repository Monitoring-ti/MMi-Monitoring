"""Shell UI Monitoring (Tailwind) para paginas vitrina MMI."""

from __future__ import annotations

from html import escape
from typing import Any

# Logos locales: reemplazar SVG en public/ (se copian a out/ al generar vitrina).
LOGO_SIDEBAR = "/monitoring-logo-horizontal.svg"
LOGO_HEADER = "/monitoring-logo-horizontal.svg"
FOOTER_CREDIT = "Desarrollado por P.H.R. para Monitoring · sep 26 · v0.1"

NAV_ITEMS: tuple[tuple[str, str, str, str], ...] = (
    ("home", "index.html", "dashboard", "Inicio"),
    ("pruebas", "pruebas.html", "science", "Pruebas"),
    ("ejemplos", "ejemplos.html", "menu_book", "Ejemplos"),
    ("search", "search.html", "search", "Búsqueda"),
    ("rag", "rag.html", "psychology", "Consulta RAG"),
)

TAILWIND_CONFIG = """
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "on-primary": "#ffffff",
        "on-error-container": "#93000a",
        "secondary-fixed": "#ffdcbd",
        "secondary-container": "#fc9912",
        "on-background": "#1a1c1c",
        "tertiary-fixed": "#e1e2e6",
        "outline": "#747782",
        "on-surface": "#1a1c1c",
        "on-primary-fixed": "#001946",
        "error-container": "#ffdad6",
        "secondary": "#8a5100",
        "on-primary-container": "#92b1ff",
        "on-tertiary": "#ffffff",
        "tertiary-fixed-dim": "#c5c6ca",
        "tertiary": "#2c2f32",
        "surface-variant": "#e2e2e2",
        "on-tertiary-container": "#b1b2b6",
        "on-secondary-container": "#643900",
        "surface-bright": "#f9f9f9",
        "primary-fixed-dim": "#b1c5ff",
        "on-error": "#ffffff",
        "primary-container": "#1a418c",
        "surface": "#f9f9f9",
        "inverse-primary": "#b1c5ff",
        "primary-fixed": "#dae2ff",
        "primary": "#002a6d",
        "tertiary-container": "#434548",
        "background": "#f9f9f9",
        "surface-container": "#eeeeee",
        "surface-container-highest": "#e2e2e2",
        "on-secondary-fixed": "#2c1600",
        "inverse-surface": "#2f3131",
        "surface-tint": "#395ba8",
        "on-secondary": "#ffffff",
        "error": "#ba1a1a",
        "surface-container-lowest": "#ffffff",
        "surface-container-high": "#e8e8e8",
        "on-surface-variant": "#434651",
        "inverse-on-surface": "#f0f1f1",
        "surface-dim": "#dadada",
      },
      borderRadius: { DEFAULT: "0.125rem", lg: "0.25rem", xl: "0.5rem", full: "0.75rem" },
      spacing: {
        "stack-md": "16px", "margin-mobile": "16px", "margin-desktop": "40px",
        "base": "4px", "stack-sm": "8px", "gutter": "24px", "stack-lg": "32px",
      },
      fontFamily: { sans: ["Montserrat", "system-ui", "sans-serif"] },
    },
  },
};
"""


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
        f'<span class="material-symbols-outlined">{escape(icon)}</span>'
        f'<span class="text-body-md font-medium">{escape(label)}</span></a></li>'
    )


def _mobile_nav(key: str, page: str, icon: str, label: str, active: str) -> str:
    is_active = key == active
    if is_active:
        wrap = "flex flex-col items-center justify-center bg-secondary-container text-on-secondary-container rounded-full px-4 py-1"
    else:
        wrap = "flex flex-col items-center justify-center text-on-surface-variant"
    return (
        f'<a href="{_href(page)}" class="{wrap}">'
        f'<span class="material-symbols-outlined">{escape(icon)}</span>'
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
) -> str:
    bar = ""
    if progress_pct is not None:
        bar = f"""
<div class="w-full bg-surface-container h-2 rounded-full overflow-hidden mt-base">
  <div class="bg-primary h-full rounded-full" style="width:{int(progress_pct)}%"></div>
</div>"""
    return f"""
<div class="bg-surface-container-lowest p-stack-lg rounded-lg border border-outline/20 shadow-sm hover:shadow-md transition-shadow">
  <div class="flex justify-between items-start mb-stack-md">
    <div class="p-stack-sm {icon_bg} rounded-xl {icon_color}">
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
) -> str:
    nav = "".join(_nav_link(k, p, i, l, active) for k, p, i, l in NAV_ITEMS)
    mobile = "".join(_mobile_nav(k, p, i, l, active) for k, p, i, l in NAV_ITEMS)
    fab_html = ""
    if show_fab:
        fab_html = f"""
  <a href="{_href('rag.html')}" class="fixed bottom-20 md:bottom-margin-desktop right-margin-mobile w-14 h-14 bg-secondary-container text-on-secondary-container rounded-full flex items-center justify-center shadow-lg hover:scale-105 transition-all z-40" title="Consulta RAG">
    <span class="material-symbols-outlined" style="font-size:28px;font-variation-settings:'FILL' 1">psychology</span>
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
<title>{escape(title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=block" rel="stylesheet"/>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<script id="tailwind-config">try{{{TAILWIND_CONFIG}}}catch(_e){{}}</script>
<style>
  body {{ font-family: Montserrat, system-ui, sans-serif; }}
  .material-symbols-outlined {{ font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }}
</style>
{extra_head}
</head>
<body class="flex min-h-screen text-on-surface bg-background">
<aside class="hidden md:flex flex-col w-64 bg-primary text-on-primary fixed h-full z-50">
  <div class="p-stack-lg flex items-center gap-base">
    <div class="w-full bg-white rounded-lg p-stack-sm shadow-sm">
      <img src="{LOGO_SIDEBAR}" alt="Monitoring" class="w-full h-auto object-contain"/>
    </div>
  </div>
  <nav class="flex-1 mt-stack-md"><ul class="space-y-base">{nav}</ul></nav>
  <div class="p-margin-mobile mt-auto">
    <div class="bg-primary-container rounded-lg p-stack-md">
      <p class="text-label-sm text-on-primary-container opacity-80 uppercase mb-base tracking-wider">Corpus activo</p>
      <div class="flex items-center justify-between gap-stack-sm">
        <span class="text-body-md font-bold">{escape(corpus_lote)}</span>
        <span class="material-symbols-outlined text-secondary-container">verified</span>
      </div>
      <p class="text-label-sm text-on-primary-container opacity-70 mt-base">MMI · consulta documental</p>
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
        <span class="material-symbols-outlined text-outline" style="font-size:20px">search</span>
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
<nav class="md:hidden fixed bottom-0 w-full bg-surface flex justify-around items-center py-2 px-margin-mobile shadow-lg border-t border-outline/20 z-50">{mobile}</nav>
{footer_scripts}
</body></html>"""
