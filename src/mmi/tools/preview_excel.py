"""CLI: extrae un Excel y genera JSON + Markdown + HTML para inspeccionar."""

from __future__ import annotations

import argparse
import json
import webbrowser
from dataclasses import asdict
from html import escape
from pathlib import Path

from mmi.ingest.excel import ExcelAdapter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extrae un XLSX y genera vista JSON/MD/HTML."
    )
    parser.add_argument("xlsx", type=Path, help="Ruta al archivo .xlsx")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("out/excel-preview"),
        help="Carpeta de salida (default: out/excel-preview)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Abrir el HTML en el navegador al terminar",
    )
    parser.add_argument(
        "--max-rows-html",
        type=int,
        default=500,
        help="Máximo de filas por hoja en el HTML (default 500)",
    )
    args = parser.parse_args(argv)

    path = args.xlsx
    if not path.exists():
        raise SystemExit(f"No existe: {path}")

    doc = ExcelAdapter().extract(path)
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "source_path": doc.source_path,
        "quality": doc.quality,
        "notes": doc.notes,
        "meta": doc.meta,
        "sheets": [asdict(s) for s in doc.sheets],
        "records": [
            {
                "sheet": r.sheet,
                "row": r.row,
                "values": r.values,
                "text_line": r.text_line,
            }
            for r in doc.records
        ],
    }

    json_path = out_dir / "extracted.json"
    md_path = out_dir / "extracted.md"
    html_path = out_dir / "extracted.html"

    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(doc.markdown, encoding="utf-8")
    html_path.write_text(
        _render_html(doc, max_rows=args.max_rows_html), encoding="utf-8"
    )

    print(f"quality: {doc.quality}")
    print(f"sheets:  {len(doc.sheets)}")
    print(f"records: {len(doc.records)}")
    for s in doc.sheets:
        print(
            f"  - {s.name}: {s.status}, header_row={s.header_row}, "
            f"data_rows={s.data_rows}, cols={len(s.columns)}"
        )
    if doc.notes:
        print("notes:")
        for n in doc.notes:
            print(f"  · {n}")
    print(f"wrote: {json_path}")
    print(f"wrote: {md_path}")
    print(f"wrote: {html_path}")

    if args.open:
        webbrowser.open(html_path.resolve().as_uri())
    return 0


def _render_html(doc, max_rows: int) -> str:
    sheets_nav = []
    sheets_body = []
    for i, sheet in enumerate(doc.sheets):
        sid = f"sheet-{i}"
        sheets_nav.append(
            f'<a class="pill" href="#{sid}">{escape(sheet.name)} '
            f'<span class="muted">({sheet.data_rows})</span></a>'
        )
        rows = [r for r in doc.records if r.sheet == sheet.name][:max_rows]
        if not sheet.columns:
            table = "<p class='warn'>Sin columnas / sin datos.</p>"
        else:
            head = (
                "<tr><th>excel_row</th>"
                + "".join(f"<th>{escape(c)}</th>" for c in sheet.columns)
                + "</tr>"
            )
            body_rows = []
            for r in rows:
                tds = "".join(
                    f"<td>{escape(r.values.get(c) or '∅')}</td>" for c in sheet.columns
                )
                body_rows.append(f"<tr><td class='rownum'>{r.row}</td>{tds}</tr>")
            truncated = ""
            if sheet.data_rows > max_rows:
                truncated = (
                    f"<p class='muted'>Mostrando {max_rows} de {sheet.data_rows} "
                    f"filas. El JSON tiene el resto.</p>"
                )
            table = truncated + f"<table><thead>{head}</thead><tbody>" + "".join(
                body_rows
            ) + "</tbody></table>"

        sheets_body.append(
            f"""
<section id="{sid}" class="card">
  <h2>{escape(sheet.name)}</h2>
  <p class="meta">status=<b>{escape(sheet.status)}</b> ·
     header_row={sheet.header_row} · data_rows={sheet.data_rows}</p>
  {table}
</section>
"""
        )

    notes = ""
    if doc.notes:
        notes = (
            "<div class='card notes'><h2>Notas de calidad</h2><ul>"
            + "".join(f"<li>{escape(n)}</li>" for n in doc.notes)
            + "</ul></div>"
        )

    qclass = {"pass": "ok", "review": "warn", "reject": "bad"}.get(doc.quality, "")
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>Extracción Excel — {escape(Path(doc.source_path).name)}</title>
<style>
  :root {{ font-family: Segoe UI, system-ui, sans-serif; color: #e8e8e8; background: #1a1a1a; }}
  body {{ margin: 0; padding: 24px; line-height: 1.4; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 8px; }}
  h2 {{ font-size: 1.1rem; margin: 0 0 8px; }}
  .muted {{ color: #9a9a9a; }}
  .pill {{ display: inline-block; padding: 4px 10px; margin: 0 6px 6px 0;
           border: 1px solid #3a3a3a; border-radius: 999px; color: #e8e8e8;
           text-decoration: none; font-size: 0.85rem; }}
  .pill:hover {{ background: #2a2a2a; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 6px;
            font-size: 0.8rem; font-weight: 600; }}
  .badge.ok {{ background: #1f3d2a; color: #8fddb0; }}
  .badge.warn {{ background: #3d321a; color: #e6c07b; }}
  .badge.bad {{ background: #3d1a1a; color: #e68a8a; }}
  .card {{ border: 1px solid #333; border-radius: 8px; padding: 16px;
           margin: 16px 0; background: #202020; overflow: auto; }}
  table {{ border-collapse: collapse; width: max-content; min-width: 100%;
           font-size: 0.82rem; }}
  th, td {{ border: 1px solid #333; padding: 4px 8px; vertical-align: top; }}
  th {{ background: #2a2a2a; position: sticky; top: 0; }}
  .rownum {{ color: #8ab4ff; font-variant-numeric: tabular-nums; }}
  .warn {{ color: #e6c07b; }}
  .meta {{ color: #9a9a9a; font-size: 0.85rem; }}
  input#filter {{ width: min(480px, 100%); padding: 8px 10px; border-radius: 6px;
                  border: 1px solid #444; background: #111; color: #eee; }}
</style>
</head>
<body>
  <h1>Extracción Excel</h1>
  <p class="meta">{escape(doc.source_path)}</p>
  <p>
    Calidad: <span class="badge {qclass}">{escape(doc.quality)}</span>
    · Hojas: {len(doc.sheets)}
    · Filas: {len(doc.records)}
  </p>
  <p><input id="filter" type="search" placeholder="Filtrar texto en la hoja visible…"/></p>
  <nav>{"".join(sheets_nav)}</nav>
  {notes}
  {"".join(sheets_body)}
<script>
const input = document.getElementById('filter');
input.addEventListener('input', () => {{
  const q = input.value.toLowerCase();
  document.querySelectorAll('section.card table tbody tr').forEach(tr => {{
    tr.style.display = !q || tr.innerText.toLowerCase().includes(q) ? '' : 'none';
  }});
}});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
