"""Estado Fase 0 por documento y vistas HTML de revisión."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Literal

Status = Literal[
    "pendiente",
    "pendiente_extractor",
    "pass",
    "review",
    "reject",
]


@dataclass
class AnalysisRecord:
    id: str
    name: str
    document_key: str
    revision: str
    tipo: str
    phase0: str
    extension: str
    relative_path: str
    absolute_path: str | None
    uploaded: bool
    status: Status
    quality: str | None
    sheets: int | None
    records: int | None
    indexable: bool
    notes: list[str]
    extract_dir: str | None
    review_url: str | None
    extracted_at: str | None
    status_label: str
    status_detail: str


def slug_for_path(path: Path) -> str:
    return path.stem.replace(" ", "_")[:60]


def _find_extract_dir(extract_root: Path, absolute_path: str | None) -> Path | None:
    if not absolute_path or not extract_root.exists():
        return None
    slug = slug_for_path(Path(absolute_path))
    candidate = extract_root / slug
    if (candidate / "extracted.json").exists():
        return candidate
    for child in extract_root.iterdir():
        if not child.is_dir():
            continue
        meta = child / "extracted.json"
        if not meta.exists():
            continue
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("source_path") == absolute_path:
            return child
    return None


def _status_label(status: Status) -> tuple[str, str]:
    labels = {
        "pendiente": ("Pendiente", "Subido al corpus; falta extracción"),
        "pendiente_extractor": ("Pendiente extractor", "Extractor PDF/PPTX/OCR aún no conectado"),
        "pass": ("OK — listo", "Extracción aprobada; apto para indexar"),
        "review": ("Revisar", "Extracción con observaciones; revisar antes de indexar"),
        "reject": ("Rechazado", "No cumple calidad mínima (p. ej. plantilla vacía)"),
    }
    return labels.get(status, (status, ""))


def collect_analysis_status(
    manifest_path: Path,
    extract_root: Path,
    reviews_subdir: str = "lote1-extract",
) -> dict[str, Any]:
    if not manifest_path.exists():
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": f"No existe manifest: {manifest_path}",
            "summary": {},
            "analyses": [],
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    analyses: list[AnalysisRecord] = []

    for entry in manifest.get("files") or []:
        abs_path = entry.get("absolute_path")
        phase0 = entry.get("phase0", "")
        extract_dir = _find_extract_dir(extract_root, abs_path)
        quality: str | None = None
        sheets: int | None = None
        records: int | None = None
        notes: list[str] = []
        extracted_at: str | None = None
        review_url: str | None = None
        status: Status

        if extract_dir and (extract_dir / "extracted.json").exists():
            data = json.loads((extract_dir / "extracted.json").read_text(encoding="utf-8"))
            quality = data.get("quality")
            fmt = data.get("format") or data.get("meta", {}).get("format")
            if fmt == "pptx":
                sheets = data.get("slide_count") or data.get("meta", {}).get("slide_count")
                records = data.get("slides_pass") or data.get("meta", {}).get("slides_pass")
            elif fmt == "docx":
                sheets = data.get("block_count") or data.get("meta", {}).get("block_count")
                records = data.get("blocks_pass") or data.get("meta", {}).get("blocks_pass")
            elif fmt in {"pdf", "ocr"} or data.get("pages"):
                pages = data.get("pages") or []
                sheets = data.get("meta", {}).get("page_count") or len(pages)
                records = data.get("meta", {}).get("pages_with_text") or sum(
                    1 for p in pages if (p.get("text") or p.get("text_raw"))
                )
            else:
                sheets = len(data.get("sheets") or [])
                records = len(data.get("records") or [])
            notes = list(data.get("notes") or [])
            ts = (extract_dir / "extracted.json").stat().st_mtime
            extracted_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            status = quality if quality in {"pass", "review", "reject"} else "review"
            rel_review = f"{reviews_subdir}/{extract_dir.name}/review.html"
            if (extract_dir / "review.html").exists():
                review_url = rel_review
        elif phase0 in {"pdf", "pptx", "ocr", "docx"}:
            status = "pendiente_extractor"
        else:
            status = "pendiente"

        label, detail = _status_label(status)
        analyses.append(
            AnalysisRecord(
                id=entry.get("id", ""),
                name=entry.get("name", ""),
                document_key=entry.get("document_key", ""),
                revision=entry.get("revision", ""),
                tipo=entry.get("suggested_tipo", ""),
                phase0=phase0,
                extension=entry.get("extension", ""),
                relative_path=entry.get("relative_path", ""),
                absolute_path=abs_path,
                uploaded=bool(entry.get("ready")),
                status=status,
                quality=quality,
                sheets=sheets,
                records=records,
                indexable=status == "pass",
                notes=notes,
                extract_dir=str(extract_dir) if extract_dir else None,
                review_url=review_url,
                extracted_at=extracted_at,
                status_label=label,
                status_detail=detail,
            )
        )

    summary = {
        "total": len(analyses),
        "uploaded": sum(1 for a in analyses if a.uploaded),
        "pass": sum(1 for a in analyses if a.status == "pass"),
        "review": sum(1 for a in analyses if a.status == "review"),
        "reject": sum(1 for a in analyses if a.status == "reject"),
        "pendiente": sum(1 for a in analyses if a.status == "pendiente"),
        "pendiente_extractor": sum(1 for a in analyses if a.status == "pendiente_extractor"),
        "indexable": sum(1 for a in analyses if a.indexable),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lote": manifest.get("lote"),
        "policy": manifest.get("policy"),
        "manifest_path": str(manifest_path),
        "extract_root": str(extract_root),
        "summary": summary,
        "analyses": [a.__dict__ for a in analyses],
    }


def render_review_html(data: dict[str, Any], max_rows: int = 500) -> str:
    fmt = data.get("format") or data.get("meta", {}).get("format")
    if fmt == "pptx":
        return _render_pptx_review(data, max_slides=max_rows)
    if fmt == "docx":
        return _render_docx_review(data, max_blocks=max_rows)
    if fmt in {"pdf", "ocr"} or data.get("pages"):
        return _render_pdf_review(data, max_pages=max_rows)
    return _render_excel_review(data, max_rows=max_rows)


def _render_docx_review(data: dict[str, Any], max_blocks: int = 200) -> str:
    source = data.get("source_path", "")
    quality = data.get("quality", "review")
    notes = data.get("notes") or []
    meta = data.get("meta") or {}
    blocks: list[dict[str, Any]] = list(data.get("blocks") or [])

    qclass = {"pass": "ok", "review": "warn", "reject": "bad"}.get(quality, "")
    nav: list[str] = []
    body: list[str] = []

    for block in blocks[:max_blocks]:
        idx = block.get("block_index", 0)
        btype = block.get("block_type", "paragraph")
        section = block.get("section_path", "")
        q = block.get("extraction_quality", "pass")
        bclass = {"pass": "ok", "review": "warn", "reject": "bad"}.get(q, "")
        anchor = f"block-{idx}"
        nav.append(
            f'<a href="#{anchor}" class="badge {bclass}">#{idx} {escape(btype)}</a>'
        )
        text = block.get("markdown") or block.get("text_raw") or ""
        body.append(
            f"""<section class="card" id="{anchor}">
  <h2>Bloque {idx} <span class="badge {bclass}">{escape(btype)}</span></h2>
  <p class="meta">Sección: {escape(section)} · Calidad: {escape(q)}</p>
  <pre>{escape(text[:8000])}</pre>
</section>"""
        )

    notes_html = ""
    if notes:
        notes_html = "<ul>" + "".join(f"<li>{escape(n)}</li>" for n in notes) + "</ul>"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>{escape(Path(source).name)} — revisión DOCX</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #1a1a1a; color: #e8e8e8;
         margin: 0; padding: 20px; line-height: 1.45; }}
  a {{ color: #8ab4ff; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;
            margin: 2px; text-decoration: none; }}
  .badge.ok {{ background: #1a3d1a; color: #8ae68a; }}
  .badge.warn {{ background: #3d351a; color: #e6c07b; }}
  .badge.bad {{ background: #3d1a1a; color: #e68a8a; }}
  .card {{ border: 1px solid #333; border-radius: 8px; padding: 16px;
           margin: 16px 0; background: #202020; }}
  pre {{ white-space: pre-wrap; word-break: break-word; font-size: 0.85rem; }}
  .meta {{ color: #9a9a9a; font-size: 0.85rem; }}
  nav {{ margin: 12px 0; line-height: 2; }}
</style>
</head>
<body>
  <p><a href="../../analysis-status.html">← Volver al estado de análisis</a></p>
  <h1>{escape(Path(source).name)}</h1>
  <p class="meta">{escape(source)}</p>
  <p>Calidad: <span class="badge {qclass}">{escape(quality)}</span>
     · Bloques: {meta.get('block_count', len(blocks))}
     · Headings: {meta.get('heading_count', '?')} · Tablas: {meta.get('table_count', '?')}</p>
  {notes_html}
  <nav>{"".join(nav)}</nav>
  {"".join(body)}
</body>
</html>"""


def _render_pptx_review(data: dict[str, Any], max_slides: int = 80) -> str:
    source = data.get("source_path", "")
    quality = data.get("quality", "review")
    notes = data.get("notes") or []
    meta = data.get("meta") or {}
    slides: list[dict[str, Any]] = list(data.get("slides") or [])

    qclass = {"pass": "ok", "review": "warn", "reject": "bad"}.get(quality, "")
    nav: list[str] = []
    body: list[str] = []

    for slide in slides[:max_slides]:
        num = slide.get("slide_number", 0)
        sid = f"slide-{num}"
        title = slide.get("slide_title", "")
        eq = slide.get("extraction_quality", "")
        nav.append(
            f'<a class="pill" href="#{sid}">Slide {num} · {escape(title[:40])} '
            f'<span class="muted">({eq})</span></a>'
        )
        elements_html: list[str] = []
        for el in slide.get("elements") or []:
            kind = el.get("kind", "")
            if el.get("markdown"):
                elements_html.append(
                    f"<h3>{escape(kind)}</h3><pre class='page-text'>{escape(el['markdown'])}</pre>"
                )
            elif el.get("text"):
                elements_html.append(
                    f"<h3>{escape(kind)}</h3><pre class='page-text'>{escape(el['text'])}</pre>"
                )
            elif el.get("media_ref"):
                elements_html.append(
                    f"<p class='warn'>Imagen {escape(el['media_ref'])} — análisis visual pendiente</p>"
                )
        notes_slide = slide.get("speaker_notes") or ""
        notes_block = (
            f"<p><b>Notas:</b></p><pre class='page-text'>{escape(notes_slide)}</pre>"
            if notes_slide
            else ""
        )
        section = slide.get("section_title") or ""
        body.append(
            f"""<section id="{sid}" class="card">
  <h2>Diapositiva {num}: {escape(title)}</h2>
  <p class="meta">Sección: {escape(section)} · calidad={escape(eq)}</p>
  {"".join(elements_html) or "<p class='warn'>Sin elementos de texto</p>"}
  {notes_block}
</section>"""
        )

    if len(slides) > max_slides:
        body.append(f"<p class='muted'>Mostrando {max_slides} de {len(slides)} diapositivas.</p>")

    notes_html = ""
    if notes:
        notes_html = (
            "<div class='card notes'><h2>Notas de calidad</h2><ul>"
            + "".join(f"<li>{escape(str(n))}</li>" for n in notes)
            + "</ul></div>"
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>Revisión PPTX — {escape(Path(source).name)}</title>
<style>
  :root {{ font-family: Segoe UI, system-ui, sans-serif; color: #e8e8e8; background: #1a1a1a; }}
  body {{ margin: 0; padding: 24px; line-height: 1.4; }}
  a {{ color: #8ab4ff; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 8px; }}
  h2 {{ font-size: 1.1rem; margin: 0 0 8px; }}
  h3 {{ font-size: 0.95rem; margin: 12px 0 6px; color: #bbb; }}
  .muted {{ color: #9a9a9a; }}
  .pill {{ display: inline-block; padding: 4px 10px; margin: 0 6px 6px 0;
           border: 1px solid #3a3a3a; border-radius: 999px; color: #e8e8e8;
           text-decoration: none; font-size: 0.85rem; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 6px;
            font-size: 0.8rem; font-weight: 600; }}
  .badge.ok {{ background: #1f3d2a; color: #8fddb0; }}
  .badge.warn {{ background: #3d321a; color: #e6c07b; }}
  .badge.bad {{ background: #3d1a1a; color: #e68a8a; }}
  .card {{ border: 1px solid #333; border-radius: 8px; padding: 16px;
           margin: 16px 0; background: #202020; overflow: auto; }}
  .page-text {{ white-space: pre-wrap; word-break: break-word; font-size: 0.82rem;
                background: #181818; padding: 12px; border-radius: 6px; border: 1px solid #333; }}
  .warn {{ color: #e6c07b; }}
  .meta {{ color: #9a9a9a; font-size: 0.85rem; }}
</style>
</head>
<body>
  <p><a href="../../analysis-status.html">← Volver al estado de análisis</a></p>
  <h1>{escape(Path(source).name)}</h1>
  <p class="meta">{escape(source)}</p>
  <p>Calidad: <span class="badge {qclass}">{escape(quality)}</span>
     · Diapositivas: {meta.get('slide_count', len(slides))}
     · Indexables: {meta.get('slides_pass', 0)}</p>
  <nav>{"".join(nav)}</nav>
  {notes_html}
  {"".join(body)}
</body>
</html>"""


def _render_pdf_review(data: dict[str, Any], max_pages: int = 50) -> str:
    source = data.get("source_path", "")
    quality = data.get("quality", "review")
    notes = data.get("notes") or []
    pages = data.get("pages") or []
    meta = data.get("meta") or {}

    qclass = {"pass": "ok", "review": "warn", "reject": "bad"}.get(quality, "")
    nav: list[str] = []
    body: list[str] = []

    for pg in pages[:max_pages]:
        num = pg.get("page", 0)
        sid = f"page-{num}"
        chars = pg.get("char_count", 0)
        ocr = pg.get("needs_ocr", False)
        label = f"Pág {num}" + (" · OCR" if ocr else "")
        nav.append(f'<a class="pill" href="#{sid}">{escape(label)} <span class="muted">({chars})</span></a>')
        text = pg.get("text") or ""
        if ocr or not text:
            content = "<p class='warn'>Sin texto nativo — requiere OCR.</p>"
        else:
            shown = escape(text if len(text) <= 8000 else text[:8000] + "\n\n…")
            content = f"<pre class='page-text'>{shown}</pre>"
        body.append(
            f"""<section id="{sid}" class="card">
  <h2>Página {num}</h2>
  <p class="meta">{chars} caracteres · {'OCR pendiente' if ocr else 'texto nativo'}</p>
  {content}
</section>"""
        )

    if len(pages) > max_pages:
        body.append(f"<p class='muted'>Mostrando {max_pages} de {len(pages)} páginas.</p>")

    notes_html = ""
    if notes:
        notes_html = (
            "<div class='card notes'><h2>Notas de calidad</h2><ul>"
            + "".join(f"<li>{escape(str(n))}</li>" for n in notes)
            + "</ul></div>"
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>Revisión — {escape(Path(source).name)}</title>
<style>
  :root {{ font-family: Segoe UI, system-ui, sans-serif; color: #e8e8e8; background: #1a1a1a; }}
  body {{ margin: 0; padding: 24px; line-height: 1.4; }}
  a {{ color: #8ab4ff; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 8px; }}
  h2 {{ font-size: 1.1rem; margin: 0 0 8px; }}
  .muted {{ color: #9a9a9a; }}
  .pill {{ display: inline-block; padding: 4px 10px; margin: 0 6px 6px 0;
           border: 1px solid #3a3a3a; border-radius: 999px; color: #e8e8e8;
           text-decoration: none; font-size: 0.85rem; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 6px;
            font-size: 0.8rem; font-weight: 600; }}
  .badge.ok {{ background: #1f3d2a; color: #8fddb0; }}
  .badge.warn {{ background: #3d321a; color: #e6c07b; }}
  .badge.bad {{ background: #3d1a1a; color: #e68a8a; }}
  .card {{ border: 1px solid #333; border-radius: 8px; padding: 16px;
           margin: 16px 0; background: #202020; overflow: auto; }}
  .page-text {{ white-space: pre-wrap; word-break: break-word; font-size: 0.82rem;
                background: #181818; padding: 12px; border-radius: 6px; border: 1px solid #333; }}
  .warn {{ color: #e6c07b; }}
  .meta {{ color: #9a9a9a; font-size: 0.85rem; }}
  input#filter {{ width: min(480px, 100%); padding: 8px 10px; border-radius: 6px;
                  border: 1px solid #444; background: #111; color: #eee; }}
</style>
</head>
<body>
  <p><a href="../../analysis-status.html">← Volver al estado de análisis</a></p>
  <h1>{escape(Path(source).name)}</h1>
  <p class="meta">{escape(source)}</p>
  <p>Calidad: <span class="badge {qclass}">{escape(quality)}</span>
     · Páginas: {meta.get('page_count', len(pages))}
     · Con texto: {meta.get('pages_with_text', 0)}
     · OCR pendiente: {meta.get('pages_needs_ocr', 0)}</p>
  <p><input id="filter" type="search" placeholder="Filtrar páginas…"/></p>
  <nav>{"".join(nav)}</nav>
  {notes_html}
  {"".join(body)}
<script>
const input = document.getElementById('filter');
input.addEventListener('input', () => {{
  const q = input.value.toLowerCase();
  document.querySelectorAll('section.card').forEach(sec => {{
    if (sec.classList.contains('notes')) return;
    sec.style.display = !q || sec.innerText.toLowerCase().includes(q) ? '' : 'none';
  }});
}});
</script>
</body>
</html>"""


def _render_excel_review(data: dict[str, Any], max_rows: int = 500) -> str:
    source = data.get("source_path", "")
    quality = data.get("quality", "review")
    notes = data.get("notes") or []
    sheets = data.get("sheets") or []
    records = data.get("records") or []

    qclass = {"pass": "ok", "review": "warn", "reject": "bad"}.get(quality, "")
    sheets_nav: list[str] = []
    sheets_body: list[str] = []

    for i, sheet in enumerate(sheets):
        sid = f"sheet-{i}"
        name = sheet.get("name", f"Hoja {i}")
        data_rows = sheet.get("data_rows", 0)
        columns = sheet.get("columns") or []
        sheets_nav.append(
            f'<a class="pill" href="#{sid}">{escape(name)} '
            f'<span class="muted">({data_rows})</span></a>'
        )
        rows = [r for r in records if r.get("sheet") == name][:max_rows]
        if not columns:
            table = "<p class='warn'>Sin columnas / sin datos.</p>"
        else:
            head = (
                "<tr><th>excel_row</th>"
                + "".join(f"<th>{escape(str(c))}</th>" for c in columns)
                + "</tr>"
            )
            body_rows = []
            for r in rows:
                values = r.get("values") or {}
                tds = "".join(
                    f"<td>{escape(str(values.get(c) or '∅'))}</td>" for c in columns
                )
                body_rows.append(f"<tr><td class='rownum'>{r.get('row')}</td>{tds}</tr>")
            truncated = ""
            if data_rows > max_rows:
                truncated = (
                    f"<p class='muted'>Mostrando {max_rows} de {data_rows} filas.</p>"
                )
            table = truncated + f"<table><thead>{head}</thead><tbody>{''.join(body_rows)}</tbody></table>"

        sheets_body.append(
            f"""<section id="{sid}" class="card">
  <h2>{escape(name)}</h2>
  <p class="meta">status=<b>{escape(sheet.get('status', ''))}</b> ·
     header_row={sheet.get('header_row')} · data_rows={data_rows}</p>
  {table}
</section>"""
        )

    notes_html = ""
    if notes:
        notes_html = (
            "<div class='card notes'><h2>Notas de calidad</h2><ul>"
            + "".join(f"<li>{escape(str(n))}</li>" for n in notes)
            + "</ul></div>"
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>Revisión — {escape(Path(source).name)}</title>
<style>
  :root {{ font-family: Segoe UI, system-ui, sans-serif; color: #e8e8e8; background: #1a1a1a; }}
  body {{ margin: 0; padding: 24px; line-height: 1.4; }}
  a {{ color: #8ab4ff; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 8px; }}
  h2 {{ font-size: 1.1rem; margin: 0 0 8px; }}
  .muted {{ color: #9a9a9a; }}
  .pill {{ display: inline-block; padding: 4px 10px; margin: 0 6px 6px 0;
           border: 1px solid #3a3a3a; border-radius: 999px; color: #e8e8e8;
           text-decoration: none; font-size: 0.85rem; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 6px;
            font-size: 0.8rem; font-weight: 600; }}
  .badge.ok {{ background: #1f3d2a; color: #8fddb0; }}
  .badge.warn {{ background: #3d321a; color: #e6c07b; }}
  .badge.bad {{ background: #3d1a1a; color: #e68a8a; }}
  .card {{ border: 1px solid #333; border-radius: 8px; padding: 16px;
           margin: 16px 0; background: #202020; overflow: auto; }}
  table {{ border-collapse: collapse; width: max-content; min-width: 100%; font-size: 0.82rem; }}
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
  <p><a href="../../analysis-status.html">← Volver al estado de análisis</a></p>
  <h1>{escape(Path(source).name)}</h1>
  <p class="meta">{escape(source)}</p>
  <p>Calidad: <span class="badge {qclass}">{escape(quality)}</span>
     · Hojas: {len(sheets)} · Filas: {len(records)}</p>
  <p><input id="filter" type="search" placeholder="Filtrar filas…"/></p>
  <nav>{"".join(sheets_nav)}</nav>
  {notes_html}
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
</html>"""


def write_review_pages(extract_root: Path, max_rows: int = 500) -> int:
    count = 0
    if not extract_root.exists():
        return 0
    for child in extract_root.iterdir():
        if not child.is_dir():
            continue
        meta_path = child / "extracted.json"
        if not meta_path.exists():
            continue
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        if data.get("format") == "pptx":
            slides_path = child / "slides.json"
            if slides_path.exists():
                try:
                    data["slides"] = json.loads(slides_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    data["slides"] = []
        elif data.get("format") == "docx":
            blocks_path = child / "blocks.json"
            if blocks_path.exists():
                try:
                    data["blocks"] = json.loads(blocks_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    data["blocks"] = []
        (child / "review.html").write_text(
            render_review_html(data, max_rows=max_rows), encoding="utf-8"
        )
        count += 1
    return count


def _esc(s: str) -> str:
    return escape(s)


def render_dashboard(payload: dict[str, Any]) -> str:
    from mmi.analysis.source_panel import render_source_link_panel
    from mmi.corpus.remote_source import load_remote_source

    summary = payload.get("summary") or {}
    analyses = payload.get("analyses") or []
    source_panel = render_source_link_panel(
        payload.get("remote_source") or load_remote_source()
    )
    rows: list[str] = []

    status_class = {
        "pass": "ok",
        "review": "warn",
        "reject": "bad",
        "pendiente": "pending",
        "pendiente_extractor": "blocked",
    }

    for a in analyses:
        st = a.get("status", "pendiente")
        cls = status_class.get(st, "pending")
        review = ""
        if a.get("review_url"):
            review = f'<a class="btn" href="{_esc(a["review_url"])}">Revisar extracción</a>'
        elif a.get("extract_dir"):
            review = '<span class="muted">Sin vista HTML</span>'
        else:
            review = '<span class="muted">—</span>'

        stats = "—"
        if a.get("phase0") == "pptx" and a.get("records") is not None:
            stats = f'{a["records"]}/{a.get("sheets", "?")} diapositivas OK'
        elif a.get("phase0") == "docx" and a.get("records") is not None:
            stats = f'{a["records"]}/{a.get("sheets", "?")} bloques OK'
        elif a.get("phase0") in {"pdf", "ocr"} and a.get("records") is not None:
            stats = f'{a["records"]}/{a.get("sheets", "?")} págs con texto'
        elif a.get("records") is not None:
            stats = f'{a.get("sheets", 0)} hojas · {a["records"]} filas'

        rows.append(
            f"""<tr class="row" data-status="{st}" data-tipo="{_esc(a.get('tipo',''))}"
  data-phase0="{_esc(a.get('phase0',''))}" data-q="{_esc((a.get('name','') + ' ' + a.get('document_key','')).lower())}">
  <td><span class="status {cls}">{_esc(a.get('status_label', st))}</span></td>
  <td class="name">{_esc(a.get('name',''))}</td>
  <td>{_esc(a.get('document_key',''))}</td>
  <td>{_esc(a.get('revision',''))}</td>
  <td><span class="tag">{_esc(a.get('tipo',''))}</span></td>
  <td>{_esc(a.get('phase0',''))}</td>
  <td>{stats}</td>
  <td class="muted small">{_esc(a.get('status_detail',''))}</td>
  <td>{review}</td>
</tr>"""
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>MMI — Estado por análisis</title>
<style>
  :root {{ font-family: Segoe UI, system-ui, sans-serif; color: #e8e8e8; background: #1a1a1a; }}
  body {{ margin: 0; padding: 20px 24px 48px; }}
  h1 {{ font-size: 1.3rem; margin: 0 0 6px; }}
  .meta {{ color: #9a9a9a; margin-bottom: 16px; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }}
  .card-stat {{ background: #202020; border: 1px solid #333; border-radius: 8px;
    padding: 12px 16px; min-width: 120px; }}
  .card-stat b {{ display: block; font-size: 1.4rem; }}
  .card-stat span {{ color: #9a9a9a; font-size: 0.8rem; }}
  .card-stat.ok b {{ color: #8fddb0; }}
  .card-stat.warn b {{ color: #e6c07b; }}
  .card-stat.bad b {{ color: #e68a8a; }}
  .toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
  input, select {{ padding: 8px 10px; border-radius: 6px; border: 1px solid #444;
    background: #111; color: #eee; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th, td {{ border-bottom: 1px solid #333; padding: 8px; text-align: left; vertical-align: top; }}
  th {{ position: sticky; top: 0; background: #202020; z-index: 1; }}
  tr.hidden {{ display: none; }}
  .name {{ font-weight: 600; max-width: 280px; word-break: break-word; }}
  .small {{ font-size: 0.78rem; max-width: 220px; }}
  .status {{ font-size: 0.75rem; padding: 3px 8px; border-radius: 999px; white-space: nowrap; }}
  .status.ok {{ background: #1f3d2a; color: #8fddb0; }}
  .status.warn {{ background: #3d321a; color: #e6c07b; }}
  .status.bad {{ background: #3d1a1a; color: #e68a8a; }}
  .status.pending {{ background: #2a2a2a; color: #bbb; }}
  .status.blocked {{ background: #1a2f4d; color: #8ab4ff; }}
  .tag {{ font-size: 0.72rem; background: #2a2a2a; padding: 2px 7px; border-radius: 4px; }}
  a.btn {{ color: #fff; background: #2b5cff; padding: 5px 10px; border-radius: 6px;
    text-decoration: none; font-size: 0.78rem; white-space: nowrap; }}
  a.btn:hover {{ filter: brightness(1.1); }}
  .links {{ margin-top: 12px; }}
  .links a {{ color: #8ab4ff; margin-right: 14px; }}
</style>
</head>
<body>
  <h1>Estado por análisis — Fase 0</h1>
  <p class="meta">{_esc(payload.get('policy') or '')}<br/>
     Actualizado: {_esc(payload.get('generated_at', ''))} · Lote: {_esc(str(payload.get('lote', '')))}</p>
  {source_panel}
  <div class="cards">
    <div class="card-stat"><b>{summary.get('total', 0)}</b><span>Total análisis</span></div>
    <div class="card-stat ok"><b>{summary.get('pass', 0)}</b><span>OK (indexables)</span></div>
    <div class="card-stat warn"><b>{summary.get('review', 0)}</b><span>Revisar</span></div>
    <div class="card-stat bad"><b>{summary.get('reject', 0)}</b><span>Rechazados</span></div>
    <div class="card-stat"><b>{summary.get('pendiente', 0)}</b><span>Pend. extracción</span></div>
    <div class="card-stat"><b>{summary.get('pendiente_extractor', 0)}</b><span>Pend. PDF/OCR</span></div>
  </div>
  <div class="toolbar">
    <input id="q" type="search" placeholder="Buscar documento o clave…" style="min-width:240px"/>
    <select id="status">
      <option value="">Todos los estados</option>
      <option value="pass">OK</option>
      <option value="review">Revisar</option>
      <option value="reject">Rechazado</option>
      <option value="pendiente">Pendiente extracción</option>
      <option value="pendiente_extractor">Pendiente PDF/OCR</option>
    </select>
    <select id="tipo">
      <option value="">Todos los tipos</option>
      <option value="guia">guía</option>
      <option value="norma">norma</option>
      <option value="sop">sop</option>
      <option value="tabla">tabla</option>
      <option value="presentacion">presentación</option>
      <option value="plano">plano</option>
    </select>
  </div>
  <table>
    <thead>
      <tr>
        <th>Estado</th><th>Documento</th><th>Clave</th><th>Rev</th><th>Tipo</th>
        <th>Fase 0</th><th>Datos</th><th>Detalle</th><th>Revisar</th>
      </tr>
    </thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  <p class="links">
    <a href="source-review.html">Enlace carpeta (SharePoint/OneDrive)</a>
    <a href="search.html">Búsqueda con citas</a>
    <a href="corpus-picker.html">Selector de corpus</a>
    <a href="process-manifest.json">Manifest JSON</a>
    <a href="analysis-status.json">Estado JSON</a>
  </p>
<script>
const q = document.getElementById('q');
const status = document.getElementById('status');
const tipo = document.getElementById('tipo');
function applyFilter() {{
  const qq = q.value.toLowerCase().trim();
  const st = status.value;
  const tp = tipo.value;
  document.querySelectorAll('tbody tr.row').forEach(tr => {{
    const okQ = !qq || tr.dataset.q.includes(qq);
    const okS = !st || tr.dataset.status === st;
    const okT = !tp || tr.dataset.tipo === tp;
    tr.classList.toggle('hidden', !(okQ && okS && okT));
  }});
}}
q.addEventListener('input', applyFilter);
status.addEventListener('change', applyFilter);
tipo.addEventListener('change', applyFilter);
</script>
</body>
</html>"""
