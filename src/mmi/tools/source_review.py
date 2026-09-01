"""Página mínima: pegar enlace de carpeta remota para revisar archivos."""

from __future__ import annotations

import argparse
from pathlib import Path

from mmi.analysis.source_panel import render_source_link_panel
from mmi.corpus.remote_source import load_remote_source, save_remote_source


def render_source_review_page(remote: dict | None = None) -> str:
    from mmi.analysis.review_shell import render_review_nav, review_nav_css

    panel = render_source_link_panel(remote)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MMI — Revisar archivos (enlace)</title>
<style>
  :root {{ font-family: Segoe UI, system-ui, sans-serif; color: #e8e8e8; background: #1a1a1a; }}
  body {{ margin: 0; padding: 24px; max-width: 920px; }}
  h1 {{ font-size: 1.25rem; margin: 0 0 8px; }}
  .lead {{ color: #9a9a9a; margin-bottom: 20px; line-height: 1.5; }}
{review_nav_css()}
</style>
</head>
<body>
  {render_review_nav("cloud")}
  <h1>Revisar documentos en SharePoint / OneDrive</h1>
  <p class="lead">Pega el enlace compartido de la carpeta donde están los archivos.
     Guarda y abre la carpeta en una pestaña nueva para revisar los originales
     mientras consultas la extracción en el estado de análisis.</p>
  {panel}
</body>
</html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generar página para pegar enlace de carpeta remota"
    )
    parser.add_argument("--out", type=Path, default=Path("out/source-review.html"))
    parser.add_argument("--url", help="Guardar enlace al generar (SharePoint/OneDrive)")
    parser.add_argument("--label", default="", help="Etiqueta opcional de la carpeta")
    args = parser.parse_args(argv)

    remote = load_remote_source()
    if args.url:
        remote = save_remote_source(args.url, label=args.label)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_source_review_page(remote), encoding="utf-8")
    print(f"Página → {args.out.resolve()}")
    if remote and remote.get("url"):
        print(f"Enlace guardado: {remote['url'][:80]}…")
    print("Abrir vía servidor: python -m mmi.tools.serve_local → /source-review.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
