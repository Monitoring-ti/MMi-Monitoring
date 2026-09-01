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
    "error",
    "excluido",
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
    index_status: str | None = None
    index_chunks: int | None = None
    index_detail: str | None = None
    included_in_analysis: bool = True
    logical_key: str = ""
    identity_decision: str | None = None
    identity_reason: str | None = None


def load_index_lookup(out_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Mapa nombre de archivo → último resultado de indexación."""
    base = out_dir or Path("out")
    by_name: dict[str, dict[str, Any]] = {}
    for fname in ("index-lote1-summary.json", "index-corpus-summary.json"):
        path = base / fname
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = raw if isinstance(raw, list) else raw.get("results") or []
        for row in rows:
            name = row.get("archivo")
            if name:
                by_name[name] = row
    return by_name


def load_index_summary(out_dir: Path | None = None) -> dict[str, Any]:
    path = (out_dir or Path("out")) / "index-corpus-summary.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw.get("stats") or {}


def _fmt_tokens(n: int | float) -> str:
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}k"
    return f"{n:,}".replace(",", ".")


def load_token_summary(out_dir: Path | None = None) -> dict[str, Any]:
    """Tokens de chunks indexados + revisiones IA (ai-review.json)."""
    base = out_dir or Path("out")
    index_tokens = 0
    index_chunks = 0
    index_docs = 0
    top_docs: list[dict[str, Any]] = []
    updated_at: str | None = None
    progress: str | None = None

    for fname in ("index-lote1-summary.json", "index-corpus-summary.json"):
        path = base / fname
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if fname == "index-lote1-summary.json" and (base / "index-corpus-summary.json").exists():
            continue
        stats = raw.get("stats") or {}
        index_tokens = int(stats.get("tokens") or 0)
        index_chunks = int(stats.get("chunks") or 0)
        index_docs = int(stats.get("indexados") or 0)
        updated_at = raw.get("updated_at")
        progress = raw.get("progress")
        rows = [
            r
            for r in (raw.get("results") or [])
            if r.get("estado") in {"active", "indexed", "indexado"} and int(r.get("tokens") or 0) > 0
        ]
        rows.sort(key=lambda r: int(r.get("tokens") or 0), reverse=True)
        top_docs = [
            {
                "archivo": r.get("archivo", ""),
                "tokens": int(r.get("tokens") or 0),
                "chunks": int(r.get("chunks") or 0),
            }
            for r in rows[:8]
        ]
        break

    ai_reviews = 0
    ai_prompt = 0
    ai_completion = 0
    extract_root = base / "ods1-extract"
    if extract_root.exists():
        for review_path in extract_root.glob("*/ai-review.json"):
            try:
                data = json.loads(review_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            ai_reviews += 1
            usage = data.get("usage") or {}
            ai_prompt += int(usage.get("prompt_tokens") or 0)
            ai_completion += int(usage.get("completion_tokens") or 0)

    avg = round(index_tokens / index_chunks) if index_chunks else 0
    return {
        "index_tokens": index_tokens,
        "index_tokens_fmt": _fmt_tokens(index_tokens),
        "index_chunks": index_chunks,
        "index_docs": index_docs,
        "avg_tokens_per_chunk": avg,
        "ai_reviews": ai_reviews,
        "ai_prompt_tokens": ai_prompt,
        "ai_completion_tokens": ai_completion,
        "ai_total_tokens": ai_prompt + ai_completion,
        "ai_total_tokens_fmt": _fmt_tokens(ai_prompt + ai_completion),
        "updated_at": updated_at,
        "progress": progress,
        "top_docs": top_docs,
    }


def _index_label(estado: str | None) -> tuple[str, str]:
    labels = {
        "active": ("Indexado", "Activo en Qdrant/Supabase"),
        "indexed": ("Indexado", "En índice (sin activar)"),
        "indexado": ("Indexado", "En índice"),
        "duplicado": ("Duplicado", "Ya existía por hash de archivo"),
        "mismo_contenido": ("Mismo contenido", "Misma identidad lógica; texto igual — no re-indexado"),
        "needs_review": ("Identidad dudosa", "Conflicto de logical_key; clasificar manualmente"),
        "error": ("Error índice", "Falló la indexación"),
    }
    if not estado:
        return ("Pendiente índice", "Extracción OK; aún no indexado")
    return labels.get(estado, (estado, ""))


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
        "error": ("Error extracción", "Falló el extractor; reintentar o excluir"),
        "excluido": ("Excluido", "Fuera del análisis / no relevante"),
    }
    return labels.get(status, (status, ""))


def collect_analysis_status(
    manifest_path: Path,
    extract_root: Path,
    reviews_subdir: str | None = None,
    *,
    out_dir: Path | None = None,
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
    from mmi.analysis.extract_index import default_extract_roots, load_extract_index, lookup_extract
    from mmi.catalog.logical_key import DocumentIdentityMeta, derive_logical_key

    reviews_subdir = reviews_subdir or extract_root.name
    repo_out = out_dir or manifest_path.parent
    index_by_name = load_index_lookup(repo_out)
    extra_index = load_extract_index(
        default_extract_roots(), reviews_subdir=reviews_subdir
    )

    for entry in manifest.get("files") or []:
        abs_path = entry.get("absolute_path")
        phase0 = entry.get("phase0", "")
        extract_dir: Path | None = None
        quality: str | None = None
        sheets: int | None = None
        records: int | None = None
        notes: list[str] = []
        extracted_at: str | None = None
        review_url: str | None = None
        status: Status

        hit = lookup_extract(abs_path, extra_index)
        if hit and hit.get("extract_dir"):
            extract_dir = Path(hit["extract_dir"])
            quality = hit.get("quality")
            sheets = hit.get("sheets")
            records = hit.get("records")
            notes = list(hit.get("notes") or [])
            extracted_at = hit.get("extracted_at")
            review_url = hit.get("review_url")
            status = quality if quality in {"pass", "review", "reject", "error"} else "review"
        elif phase0 in {"pdf", "pptx", "ocr", "docx"}:
            status = "pendiente_extractor"
        else:
            status = "pendiente"

        if entry.get("include_in_analysis") is False:
            notes = ["Fuera del análisis (no seleccionado)"] + notes
            detail_extra = "Excluido por el usuario en el selector de corpus"
            included = False
            status = "excluido"
        else:
            detail_extra = ""
            included = True

        label, detail = _status_label(status)
        if detail_extra and status != "excluido":
            detail = f"{detail_extra}. {detail}"

        idx_row = index_by_name.get(entry.get("name", ""))
        idx_estado = idx_row.get("estado") if idx_row else None
        idx_chunks = idx_row.get("chunks") if idx_row else None
        idx_label, idx_detail = _index_label(idx_estado)
        if idx_row and idx_row.get("detalle"):
            idx_detail = str(idx_row["detalle"])[:200]

        identity_meta = DocumentIdentityMeta.from_manifest_entry(entry)
        logical_key = derive_logical_key(identity_meta)
        identity_decision: str | None = None
        identity_reason: str | None = None
        if idx_row:
            identity_decision = idx_row.get("identity_decision")
            identity_reason = idx_row.get("reason")
            metrics = idx_row.get("metrics") or {}
            if not identity_reason:
                identity_reason = metrics.get("identity_reason")
            if idx_row.get("document_key"):
                logical_key = str(idx_row["document_key"])
            if not identity_decision and idx_estado in {"needs_review", "mismo_contenido"}:
                identity_decision = idx_estado
        if idx_estado == "needs_review" and identity_reason:
            idx_detail = identity_reason[:200]

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
                indexable=status == "pass" and entry.get("include_in_analysis") is not False,
                notes=notes,
                extract_dir=str(extract_dir) if extract_dir else None,
                review_url=review_url,
                extracted_at=extracted_at,
                status_label=label,
                status_detail=detail,
                index_status=idx_estado or ("pendiente" if status == "pass" else None),
                index_chunks=int(idx_chunks) if idx_chunks is not None else None,
                index_detail=idx_detail if idx_row or status == "pass" else None,
                included_in_analysis=included,
                logical_key=logical_key,
                identity_decision=identity_decision,
                identity_reason=identity_reason,
            )
        )

    summary = {
        "total": len(analyses),
        "uploaded": sum(1 for a in analyses if a.uploaded),
        "pass": sum(1 for a in analyses if a.status == "pass"),
        "review": sum(1 for a in analyses if a.status == "review"),
        "reject": sum(1 for a in analyses if a.status == "reject"),
        "error": sum(1 for a in analyses if a.status == "error"),
        "excluidos": sum(1 for a in analyses if a.status == "excluido"),
        "pendiente": sum(1 for a in analyses if a.status == "pendiente"),
        "pendiente_extractor": sum(1 for a in analyses if a.status == "pendiente_extractor"),
        "indexable": sum(1 for a in analyses if a.indexable),
        "indexados": sum(
            1 for a in analyses if a.index_status in {"active", "indexed", "indexado"}
        ),
        "index_duplicados": sum(1 for a in analyses if a.index_status == "duplicado"),
        "index_mismo_contenido": sum(1 for a in analyses if a.index_status == "mismo_contenido"),
        "index_needs_review": sum(1 for a in analyses if a.index_status == "needs_review"),
        "index_errores": sum(1 for a in analyses if a.index_status == "error"),
        "index_pendientes": sum(
            1 for a in analyses if a.indexable and a.index_status in {None, "pendiente"}
        ),
    }

    index_summary = load_index_summary(repo_out)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lote": manifest.get("lote"),
        "policy": manifest.get("policy"),
        "corpus_root": manifest.get("corpus_root"),
        "manifest_path": str(manifest_path),
        "extract_root": str(extract_root),
        "summary": summary,
        "index_summary": index_summary,
        "token_summary": load_token_summary(repo_out),
        "analyses": [a.__dict__ for a in analyses],
    }


def render_review_html(
    data: dict[str, Any],
    max_rows: int = 500,
    *,
    extract_dir: Path | None = None,
) -> str:
    from mmi.analysis.review_panel import load_saved_review, render_review_ai_panel

    fmt = data.get("format") or data.get("meta", {}).get("format")
    name = Path(data.get("source_path", "")).name
    quality = data.get("quality") or data.get("meta", {}).get("quality") or "review"
    ai_panel = render_review_ai_panel(name, quality, load_saved_review(extract_dir))
    if fmt == "pptx":
        return _render_pptx_review(data, max_slides=max_rows, ai_panel=ai_panel)
    if fmt == "docx":
        return _render_docx_review(data, max_blocks=max_rows, ai_panel=ai_panel)
    if fmt in {"pdf", "ocr"} or data.get("pages"):
        return _render_pdf_review(data, max_pages=max_rows, ai_panel=ai_panel)
    return _render_excel_review(data, max_rows=max_rows, ai_panel=ai_panel)


def _render_docx_review(data: dict[str, Any], max_blocks: int = 200, *, ai_panel: str = "") -> str:
    from mmi.analysis.review_panel import review_back_link

    source = data.get("source_path", "")
    quality = data.get("quality", "review")
    notes = data.get("notes") or []
    meta = data.get("meta") or {}
    blocks: list[dict[str, Any]] = list(data.get("blocks") or [])

    qclass = {"pass": "ok", "review": "warn", "reject": "bad", "error": "bad"}.get(quality, "")
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
  {review_back_link()}
  <h1>{escape(Path(source).name)}</h1>
  <p class="meta">{escape(source)}</p>
  <p>Calidad: <span class="badge {qclass}">{escape(quality)}</span>
     · Bloques: {meta.get('block_count', len(blocks))}
     · Headings: {meta.get('heading_count', '?')} · Tablas: {meta.get('table_count', '?')}</p>
  {ai_panel}
  {notes_html}
  <nav>{"".join(nav)}</nav>
  {"".join(body)}
</body>
</html>"""


def _render_pptx_review(data: dict[str, Any], max_slides: int = 80, *, ai_panel: str = "") -> str:
    from mmi.analysis.review_panel import review_back_link

    source = data.get("source_path", "")
    quality = data.get("quality", "review")
    notes = data.get("notes") or []
    meta = data.get("meta") or {}
    slides: list[dict[str, Any]] = list(data.get("slides") or [])

    qclass = {"pass": "ok", "review": "warn", "reject": "bad", "error": "bad"}.get(quality, "")
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
  {review_back_link()}
  <h1>{escape(Path(source).name)}</h1>
  <p class="meta">{escape(source)}</p>
  <p>Calidad: <span class="badge {qclass}">{escape(quality)}</span>
     · Diapositivas: {meta.get('slide_count', len(slides))}
     · Indexables: {meta.get('slides_pass', 0)}</p>
  {ai_panel}
  <nav>{"".join(nav)}</nav>
  {notes_html}
  {"".join(body)}
</body>
</html>"""


def _render_pdf_review(data: dict[str, Any], max_pages: int = 50, *, ai_panel: str = "") -> str:
    from mmi.analysis.review_panel import review_back_link

    source = data.get("source_path", "")
    quality = data.get("quality", "review")
    notes = data.get("notes") or []
    pages = data.get("pages") or []
    meta = data.get("meta") or {}

    qclass = {"pass": "ok", "review": "warn", "reject": "bad", "error": "bad"}.get(quality, "")
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
  {review_back_link()}
  <h1>{escape(Path(source).name)}</h1>
  <p class="meta">{escape(source)}</p>
  <p>Calidad: <span class="badge {qclass}">{escape(quality)}</span>
     · Páginas: {meta.get('page_count', len(pages))}
     · Con texto: {meta.get('pages_with_text', 0)}
     · OCR pendiente: {meta.get('pages_needs_ocr', 0)}</p>
  {ai_panel}
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


def _render_excel_review(data: dict[str, Any], max_rows: int = 500, *, ai_panel: str = "") -> str:
    from mmi.analysis.review_panel import review_back_link

    source = data.get("source_path", "")
    quality = data.get("quality", "review")
    notes = data.get("notes") or []
    sheets = data.get("sheets") or []
    records = data.get("records") or []

    qclass = {"pass": "ok", "review": "warn", "reject": "bad", "error": "bad"}.get(quality, "")
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
  {review_back_link()}
  <h1>{escape(Path(source).name)}</h1>
  <p class="meta">{escape(source)}</p>
  <p>Calidad: <span class="badge {qclass}">{escape(quality)}</span>
     · Hojas: {len(sheets)} · Filas: {len(records)}</p>
  {ai_panel}
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
            render_review_html(data, max_rows=max_rows, extract_dir=child), encoding="utf-8"
        )
        count += 1
    return count


def _esc(s: str) -> str:
    return escape(s)


def _needs_actions(a: dict[str, Any]) -> bool:
    st = a.get("status", "")
    ix = a.get("index_status") or ""
    return st in {"reject", "review", "error"} or ix in {"error", "needs_review"}


def _action_cell(a: dict[str, Any]) -> str:
    name = _esc(a.get("name", ""))
    st = a.get("status", "")
    ix = a.get("index_status") or ""
    if ix == "needs_review" and a.get("included_in_analysis", True):
        return f"""<div class="act-group" data-doc="{name}">
  <button type="button" class="act warn" data-act="mark_verify" title="Clasificar identidad manualmente">Clasif.</button>
  <button type="button" class="act" data-act="exclude" title="Excluir del análisis">⊘</button>
</div>"""
    if st == "reject" and a.get("included_in_analysis", True):
        return f"""<div class="act-group" data-doc="{name}">
  <button type="button" class="act bad" data-act="mark_not_relevant" title="No relevante (plantilla vacía / encabezados)">No rel.</button>
  <button type="button" class="act warn" data-act="mark_verify" title="Verificar (foto escaneada / manuscrito)">Verif.</button>
  <button type="button" class="act" data-act="exclude" title="Excluir del análisis">⊘</button>
</div>"""
    if not _needs_actions(a):
        return ""
    return f"""<div class="act-group" data-doc="{name}">
  <button type="button" class="act" data-act="reextract" title="Re-extraer Fase 0">↻</button>
  <button type="button" class="act" data-act="reindex" title="Re-indexar">Idx</button>
  <button type="button" class="act warn" data-act="delete_extract" title="Eliminar extracción">✕</button>
  <button type="button" class="act" data-act="exclude" title="Excluir del análisis">⊘</button>
</div>"""


def render_dashboard(payload: dict[str, Any]) -> str:
    from mmi.analysis.review_shell import (
        render_phases_panel,
        render_review_data_links,
        render_review_nav,
        review_nav_css,
    )
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
        "error": "bad",
        "excluido": "blocked",
        "pendiente": "pending",
        "pendiente_extractor": "blocked",
    }

    index_class = {
        "active": "ok",
        "indexed": "ok",
        "indexado": "ok",
        "duplicado": "warn",
        "mismo_contenido": "warn",
        "needs_review": "bad",
        "error": "bad",
        "pendiente": "pending",
    }

    for a in analyses:
        st = a.get("status", "pendiente")
        cls = status_class.get(st, "pending")
        ix = a.get("index_status") or "pendiente"
        ix_cls = index_class.get(ix, "pending")
        ix_label, _ = _index_label(None if ix == "pendiente" else ix)
        if a.get("index_status") == "error" and a.get("index_detail"):
            ix_label = "Error índice"
        ix_chunks = a.get("index_chunks")
        ix_cell = f'<span class="status {ix_cls}">{_esc(ix_label)}</span>'
        if ix_chunks is not None and int(ix_chunks) > 0:
            ix_cell += f' <span class="muted small">{int(ix_chunks)} ch</span>'
        elif a.get("index_detail") and ix in {"error", "duplicado", "needs_review", "mismo_contenido"}:
            ix_cell += f'<br/><span class="muted small">{_esc(a.get("index_detail","")[:120])}</span>'
        if a.get("identity_decision") and a.get("identity_decision") != ix:
            ix_cell += f'<br/><span class="muted small">decisión: {_esc(a.get("identity_decision",""))}</span>'

        logical_key = a.get("logical_key") or a.get("document_key") or ""
        lk_cell = f'<span class="lk" title="{_esc(logical_key)}">{_esc(logical_key[:72])}</span>'
        if logical_key and len(logical_key) > 72:
            lk_cell += '<span class="muted small">…</span>'

        review = ""
        if a.get("review_url"):
            label = "Revisar + IA" if _needs_actions(a) else "Revisar extracción"
            review = f'<a class="btn" href="{_esc(a["review_url"])}">{label}</a>'
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

        actions = _action_cell(a)
        review_cell = review
        if actions:
            review_cell = actions + (f'<div class="rev-link">{review}</div>' if review else "")

        rows.append(
            f"""<tr class="row" data-status="{st}" data-index="{ix}" data-tipo="{_esc(a.get('tipo',''))}"
  data-phase0="{_esc(a.get('phase0',''))}" data-name="{_esc(a.get('name',''))}"
  data-included="{'1' if a.get('included_in_analysis', True) else '0'}"
  data-q="{_esc((a.get('name','') + ' ' + logical_key + ' ' + a.get('document_key','')).lower())}">
  <td><span class="status {cls}">{_esc(a.get('status_label', st))}</span></td>
  <td>{ix_cell}</td>
  <td class="name">{_esc(a.get('name',''))}</td>
  <td class="small">{lk_cell}</td>
  <td>{_esc(a.get('revision',''))}</td>
  <td><span class="tag">{_esc(a.get('tipo',''))}</span></td>
  <td>{_esc(a.get('phase0',''))}</td>
  <td>{stats}</td>
  <td class="muted small">{_esc(a.get('status_detail',''))}</td>
  <td>{review_cell}</td>
</tr>"""
        )

    idx_sum = payload.get("index_summary") or {}
    tok_sum = payload.get("token_summary") or {}
    corpus = payload.get("corpus_root") or payload.get("extract_root") or ""
    batch_total = idx_sum.get("total")
    batch_indexados = idx_sum.get("indexados")
    batch_chunks = idx_sum.get("chunks")
    progress_parts: list[str] = []
    if batch_total:
        progress_parts.append(f"batch {batch_indexados or 0}/{batch_total} indexados")
    if batch_chunks:
        progress_parts.append(f"{batch_chunks} chunks")
    if idx_sum.get("duplicados"):
        progress_parts.append(f"{idx_sum['duplicados']} dup")
    if idx_sum.get("mismo_contenido"):
        progress_parts.append(f"{idx_sum['mismo_contenido']} mismo")
    if idx_sum.get("needs_review"):
        progress_parts.append(f"{idx_sum['needs_review']} identidad")
    if idx_sum.get("errores"):
        progress_parts.append(f"{idx_sum['errores']} err")
    progress_txt = f" · {' · '.join(progress_parts)}" if progress_parts else ""

    top_token_rows = ""
    for row in tok_sum.get("top_docs") or []:
        top_token_rows += (
            f"<tr><td class='name'>{_esc(row.get('archivo',''))}</td>"
            f"<td>{_fmt_tokens(int(row.get('tokens') or 0))}</td>"
            f"<td>{int(row.get('chunks') or 0)}</td></tr>"
        )
    if not top_token_rows:
        top_token_rows = "<tr><td colspan='3' class='muted'>Sin datos de indexación aún</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>MMI — Revisión</title>
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
  .live-bar {{
    display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px;
    background: #1a2a1a; border: 1px solid #2a4a2a; border-radius: 8px;
    padding: 10px 14px; margin-bottom: 14px; font-size: 0.82rem;
  }}
  .live-dot {{
    width: 8px; height: 8px; border-radius: 50%; background: #8fddb0;
    animation: pulse 1.4s ease-in-out infinite;
  }}
  @keyframes pulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50% {{ opacity: 0.45; transform: scale(0.85); }}
  }}
  .live-bar.stale .live-dot {{ background: #888; animation: none; }}
  .live-detail {{ color: #9a9a9a; }}
  .live-detail b {{ color: #c8e6c9; font-weight: 600; }}
  #live-reload {{
    margin-left: auto; color: #8ab4ff; cursor: pointer; text-decoration: underline;
    border: none; background: none; font: inherit;
  }}
  .action-bar {{
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
    background: #251a1a; border: 1px solid #4a2a2a; border-radius: 8px;
    padding: 10px 12px; margin-bottom: 12px; font-size: 0.82rem;
  }}
  .action-bar label {{ color: #9a9a9a; }}
  button.act, button.bulk {{
    padding: 4px 8px; border-radius: 5px; border: 1px solid #444;
    background: #2a2a2a; color: #eee; cursor: pointer; font-size: 0.75rem;
  }}
  button.act:hover, button.bulk:hover {{ background: #333; }}
  button.act.warn {{ border-color: #6a3a3a; color: #e6a8a8; }}
  button.act.bad {{ border-color: #5a2a2a; color: #e68a8a; }}
  button.bulk.bad {{ border-color: #5a2a2a; color: #e68a8a; }}
  button.bulk.primary {{ background: #2b5cff; border-color: #2b5cff; color: #fff; }}
  .act-group {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px; }}
  .rev-link {{ margin-top: 4px; }}
  #action-status {{ color: #9a9a9a; min-height: 1.2em; flex: 1 1 100%; }}
  .modal-backdrop {{
    position: fixed; inset: 0; background: rgba(0,0,0,0.65); display: none;
    align-items: center; justify-content: center; z-index: 100; padding: 20px;
  }}
  .modal-backdrop.open {{ display: flex; }}
  .modal {{
    background: #202020; border: 1px solid #444; border-radius: 10px;
    max-width: 640px; width: 100%; max-height: 85vh; overflow: auto; padding: 18px 20px;
  }}
  .modal h2 {{ margin: 0 0 10px; font-size: 1.05rem; }}
  .modal pre {{
    white-space: pre-wrap; background: #141414; padding: 12px; border-radius: 6px;
    font-size: 0.82rem; border: 1px solid #333;
  }}
  .modal-actions {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
  .token-panel {{
    background: #1a2233; border: 1px solid #334466; border-radius: 10px;
    padding: 14px 16px; margin-bottom: 16px;
  }}
  .token-panel h2 {{ font-size: 1rem; margin: 0 0 10px; }}
  .token-cards {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }}
  .token-table {{ font-size: 0.82rem; max-width: 720px; }}
  .token-table th, .token-table td {{ padding: 6px 8px; }}
  .lk {{ font-family: Consolas, monospace; font-size: 0.76rem; word-break: break-all; }}
{review_nav_css()}
</style>
</head>
<body data-generated-at="{_esc(payload.get('generated_at', ''))}">
  {render_review_nav("hub")}
  <h1>Revisión — Fase 0 + índice</h1>
  <div class="live-bar" id="live-bar">
    <span class="live-dot" aria-hidden="true"></span>
    <span id="live-clock">En vivo</span>
    <span id="live-phase0" class="live-detail"></span>
    <span id="live-index" class="live-detail"></span>
    <button type="button" id="live-reload" hidden>Recargar tabla</button>
  </div>
  <p class="meta" id="meta-line">{_esc(payload.get('policy') or '')}<br/>
     Corpus: {_esc(str(corpus))}<br/>
     <span id="meta-updated">Actualizado: {_esc(payload.get('generated_at', ''))}</span>
     · Lote: {_esc(str(payload.get('lote', '')))}
     <span id="meta-progress">{progress_txt}</span></p>
  {render_phases_panel()}
  {source_panel}
  <div class="cards" id="stat-cards">
    <div class="card-stat"><b data-stat="total">{summary.get('total', 0)}</b><span>En manifest</span></div>
    <div class="card-stat ok"><b data-stat="pass">{summary.get('pass', 0)}</b><span>Fase 0 OK</span></div>
    <div class="card-stat"><b data-stat="extract_count">—</b><span>Extraídos (disco)</span></div>
    <div class="card-stat warn"><b data-stat="review">{summary.get('review', 0)}</b><span>Revisar extracción</span></div>
    <div class="card-stat bad"><b data-stat="reject">{summary.get('reject', 0)}</b><span>Rechazados</span></div>
    <div class="card-stat"><b data-stat="pend_fase0">{summary.get('pendiente', 0) + summary.get('pendiente_extractor', 0)}</b><span>Pend. Fase 0</span></div>
    <div class="card-stat ok"><b data-stat="indexados">{summary.get('indexados', 0)}</b><span>Indexados</span></div>
    <div class="card-stat warn"><b data-stat="index_duplicados">{summary.get('index_duplicados', 0)}</b><span>Dup. índice</span></div>
    <div class="card-stat warn"><b data-stat="index_mismo_contenido">{summary.get('index_mismo_contenido', 0)}</b><span>Mismo contenido</span></div>
    <div class="card-stat bad"><b data-stat="index_needs_review">{summary.get('index_needs_review', 0)}</b><span>Identidad dudosa</span></div>
    <div class="card-stat bad"><b data-stat="index_errores">{summary.get('index_errores', 0)}</b><span>Err. índice</span></div>
    <div class="card-stat"><b data-stat="index_pendientes">{summary.get('index_pendientes', 0)}</b><span>Pend. indexar</span></div>
    <div class="card-stat ok"><b data-stat="chunks">{idx_sum.get('chunks', summary.get('indexados', 0))}</b><span>Chunks (batch)</span></div>
  </div>
  <section class="token-panel" id="token-panel">
    <h2>Tokens usados</h2>
    <div class="token-cards cards">
      <div class="card-stat ok"><b data-stat="index_tokens_fmt" title="{int(tok_sum.get('index_tokens') or 0):,}">{tok_sum.get('index_tokens_fmt', '0')}</b><span>Tokens índice (chunks)</span></div>
      <div class="card-stat"><b data-stat="avg_tokens_per_chunk">{tok_sum.get('avg_tokens_per_chunk', 0)}</b><span>Promedio / chunk</span></div>
      <div class="card-stat"><b data-stat="index_tokens_raw">{f"{int(tok_sum.get('index_tokens') or 0):,}".replace(',', '.')}</b><span>Total exacto índice</span></div>
      <div class="card-stat warn"><b data-stat="ai_total_tokens_fmt">{tok_sum.get('ai_total_tokens_fmt', '0')}</b><span>OpenRouter revisión IA</span></div>
      <div class="card-stat"><b data-stat="ai_reviews">{tok_sum.get('ai_reviews', 0)}</b><span>Revisiones IA</span></div>
    </div>
    <p class="meta" id="token-meta">Batch índice: {int(tok_sum.get('index_docs') or 0)} docs · {int(tok_sum.get('index_chunks') or 0)} chunks
      · IA: {int(tok_sum.get('ai_prompt_tokens') or 0)} prompt + {int(tok_sum.get('ai_completion_tokens') or 0)} completion tokens
      {f" · actualizado {tok_sum.get('updated_at', '')[:19]}" if tok_sum.get('updated_at') else ""}</p>
    <table class="token-table">
      <thead><tr><th>Documento (top tokens)</th><th>Tokens</th><th>Chunks</th></tr></thead>
      <tbody id="top-token-rows">{top_token_rows}</tbody>
    </table>
  </section>
  <div class="toolbar">
    <input id="q" type="search" placeholder="Buscar documento o clave…" style="min-width:240px"/>
    <select id="status">
      <option value="">Estado Fase 0</option>
      <option value="pass">OK extracción</option>
      <option value="review">Revisar</option>
      <option value="reject">Rechazado</option>
      <option value="excluido">Excluido / no relevante</option>
      <option value="error">Error extracción</option>
      <option value="pendiente">Pendiente extracción</option>
      <option value="pendiente_extractor">Pendiente PDF/OCR</option>
    </select>
    <select id="index">
      <option value="">Estado índice</option>
      <option value="active">Indexado</option>
      <option value="duplicado">Duplicado</option>
      <option value="mismo_contenido">Mismo contenido</option>
      <option value="needs_review">Identidad dudosa</option>
      <option value="error">Error índice</option>
      <option value="pendiente">Pendiente índice</option>
    </select>
    <select id="tipo">
      <option value="">Todos los tipos</option>
      <option value="guia">guía</option>
      <option value="norma">norma</option>
      <option value="sop">sop</option>
      <option value="tabla">tabla</option>
      <option value="presentacion">presentación</option>
      <option value="plano">plano</option>
      <option value="manual_oem">manual OEM</option>
      <option value="otro">otro</option>
    </select>
  </div>
  <div class="action-bar" id="action-bar">
    <span class="muted">Rechazados — acciones sobre filas visibles:</span>
    <button type="button" class="bulk bad" data-bulk="mark_not_relevant" data-note="No relevante: plantilla vacía / solo encabezados Excel">No relevante</button>
    <button type="button" class="bulk warn" data-bulk="mark_verify" data-note="Verificar: posible foto escaneada o texto manuscrito (OCR)">Verificar (foto/manuscrito)</button>
    <button type="button" class="bulk" data-bulk="exclude">Excluir del análisis</button>
    <button type="button" class="bulk" data-bulk="reextract">Re-extraer</button>
    <span id="action-status"></span>
    <span class="muted" id="filter-hint"></span>
  </div>
  <table>
    <thead>
      <tr>
        <th>Fase 0</th><th>Índice</th><th>Documento</th><th>Logical key</th><th>Rev</th><th>Tipo</th>
        <th>Extractor</th><th>Datos</th><th>Detalle</th><th>Acciones</th>
      </tr>
    </thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  {render_review_data_links()}
<script>
const q = document.getElementById('q');
const status = document.getElementById('status');
const index = document.getElementById('index');
const tipo = document.getElementById('tipo');
function applyFilter() {{
  const qq = q.value.toLowerCase().trim();
  const st = status.value;
  const ix = index.value;
  const tp = tipo.value;
  document.querySelectorAll('tbody tr.row').forEach(tr => {{
    const okQ = !qq || tr.dataset.q.includes(qq);
    let okS = !st || tr.dataset.status === st;
    if (st === 'reject') okS = tr.dataset.status === 'reject';
    const okI = !ix || tr.dataset.index === ix
      || (ix === 'active' && ['active','indexed','indexado'].includes(tr.dataset.index));
    const okT = !tp || tr.dataset.tipo === tp;
    tr.classList.toggle('hidden', !(okQ && okS && okI && okT));
  }});
  const vis = [...document.querySelectorAll('tbody tr.row')].filter(tr => !tr.classList.contains('hidden')).length;
  const hint = document.getElementById('filter-hint');
  if (hint) {{
    if (st === 'reject') hint.textContent = vis + ' rechazados pendientes';
    else if (ix === 'needs_review') hint.textContent = vis + ' con identidad dudosa';
    else hint.textContent = '';
  }}
}}
q.addEventListener('input', applyFilter);
status.addEventListener('change', applyFilter);
index.addEventListener('change', applyFilter);
tipo.addEventListener('change', applyFilter);
(function initUrlFilters() {{
  const p = new URLSearchParams(location.search);
  const st = p.get('status');
  const ix = p.get('index');
  if (ix) index.value = ix;
  if (st === 'all') status.value = '';
  else if (st) status.value = st;
  else if (!ix) status.value = 'reject';
  applyFilter();
}})();

(function liveIngestion() {{
  const bar = document.getElementById('live-bar');
  const clock = document.getElementById('live-clock');
  const elPhase0 = document.getElementById('live-phase0');
  const elIndex = document.getElementById('live-index');
  const elProgress = document.getElementById('meta-progress');
  const elUpdated = document.getElementById('meta-updated');
  const btnReload = document.getElementById('live-reload');
  let knownDashboardAt = document.body.dataset.generatedAt || '';
  let lastPollAt = 0;

  function setStat(key, val) {{
    const el = document.querySelector('[data-stat="' + key + '"]');
    if (el && val !== undefined && val !== null) el.textContent = val;
  }}

  function progressText(idx) {{
    const parts = [];
    if (idx.total) parts.push('batch ' + (idx.indexados || 0) + '/' + idx.total + ' indexados');
    if (idx.chunks) parts.push(idx.chunks + ' chunks');
    if (idx.duplicados) parts.push(idx.duplicados + ' dup');
    if (idx.mismo_contenido) parts.push(idx.mismo_contenido + ' mismo');
    if (idx.needs_review) parts.push(idx.needs_review + ' identidad');
    if (idx.errores) parts.push(idx.errores + ' err');
    return parts.length ? ' · ' + parts.join(' · ') : '';
  }}

  function fmtTokens(n) {{
    n = parseInt(n, 10) || 0;
    if (n >= 1000000) return (n / 1000000).toFixed(2) + 'M';
    if (n >= 10000) return (n / 1000).toFixed(1) + 'k';
    return String(n).replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, '.');
  }}

  function applyTokenSummary(tok) {{
    if (!tok || !Object.keys(tok).length) return;
    setStat('index_tokens_fmt', tok.index_tokens_fmt || fmtTokens(tok.index_tokens));
    setStat('avg_tokens_per_chunk', tok.avg_tokens_per_chunk);
    setStat('index_tokens_raw', fmtTokens(tok.index_tokens));
    setStat('ai_total_tokens_fmt', tok.ai_total_tokens_fmt || fmtTokens(tok.ai_total_tokens));
    setStat('ai_reviews', tok.ai_reviews);
    const meta = document.getElementById('token-meta');
    if (meta) {{
      let txt = 'Batch índice: ' + (tok.index_docs || 0) + ' docs · '
        + (tok.index_chunks || 0) + ' chunks · IA: '
        + (tok.ai_prompt_tokens || 0) + ' prompt + '
        + (tok.ai_completion_tokens || 0) + ' completion tokens';
      if (tok.updated_at) txt += ' · actualizado ' + tok.updated_at.slice(0, 19);
      meta.textContent = txt;
    }}
    const tbody = document.getElementById('top-token-rows');
    if (tbody && tok.top_docs && tok.top_docs.length) {{
      tbody.innerHTML = tok.top_docs.map(function(row) {{
        return '<tr><td class="name">' + (row.archivo || '') + '</td><td>'
          + fmtTokens(row.tokens) + '</td><td>' + (row.chunks || 0) + '</td></tr>';
      }}).join('');
    }}
  }}

  function applySnapshot(data) {{
    lastPollAt = Date.now();
    bar.classList.remove('stale');
    const t = new Date(data.at || Date.now());
    clock.textContent = 'En vivo · ' + t.toLocaleTimeString();

    const s = data.summary || {{}};
    const ix = data.index_summary || {{}};
    setStat('extract_count', data.extract_count);
    if (ix.indexados !== undefined) setStat('indexados', ix.indexados);
    if (ix.duplicados !== undefined) setStat('index_duplicados', ix.duplicados);
    if (ix.mismo_contenido !== undefined) setStat('index_mismo_contenido', ix.mismo_contenido);
    if (ix.needs_review !== undefined) setStat('index_needs_review', ix.needs_review);
    if (ix.errores !== undefined) setStat('index_errores', ix.errores);
    if (ix.chunks !== undefined) setStat('chunks', ix.chunks);
    if (elProgress) elProgress.textContent = progressText(ix);
    applyTokenSummary(data.token_summary);

    const p0 = (data.phase0 || {{}}).activity;
    elPhase0.innerHTML = p0
      ? 'Fase 0: <b>[' + p0.mark + ']</b> ' + p0.file
      : (data.extract_count ? 'Fase 0: ' + data.extract_count + ' extraídos en disco' : '');

    const ixAct = (data.index || {{}}).activity;
    const ixProg = (data.index || {{}}).progress;
    if (ixAct) {{
      elIndex.innerHTML = 'Índice: <b>[' + ixAct.current + '/' + ixAct.total + ']</b> '
        + ixAct.estado + ' · ' + ixAct.chunks + ' ch · ' + ixAct.file;
    }} else if (ixProg) {{
      elIndex.textContent = 'Índice: progreso ' + ixProg;
    }} else {{
      elIndex.textContent = '';
    }}

    if (data.dashboard_generated_at && data.dashboard_generated_at !== knownDashboardAt) {{
      if (knownDashboardAt) {{
        btnReload.hidden = false;
        if (elUpdated) elUpdated.textContent = 'Tabla desactualizada · snapshot ' + data.dashboard_generated_at;
      }}
      knownDashboardAt = data.dashboard_generated_at;
    }}
  }}

  async function fetchLive() {{
    try {{
      const r = await fetch('/api/ingestion-live', {{ cache: 'no-store' }});
      if (r.ok) return await r.json();
    }} catch (_) {{}}
    const out = {{ at: new Date().toISOString(), summary: {{}}, index_summary: {{}} }};
    try {{
      const s = await fetch('analysis-status.json', {{ cache: 'no-store' }}).then(r => r.json());
      out.summary = s.summary || {{}};
      out.index_summary = s.index_summary || {{}};
      out.token_summary = s.token_summary || {{}};
      out.dashboard_generated_at = s.generated_at;
    }} catch (_) {{}}
    try {{
      const i = await fetch('index-corpus-summary.json', {{ cache: 'no-store' }}).then(r => r.json());
      if (i.stats) out.index_summary = i.stats;
      out.index = {{ progress: i.progress, updated_at: i.updated_at }};
    }} catch (_) {{}}
    return out;
  }}

  async function poll() {{
    try {{
      applySnapshot(await fetchLive());
    }} catch (_) {{
      bar.classList.add('stale');
      clock.textContent = 'Sin conexión en vivo';
    }}
    if (Date.now() - lastPollAt > 25000) bar.classList.add('stale');
  }}

  btnReload.addEventListener('click', () => location.reload());
  setInterval(poll, 5000);
  poll();
}})();

(function ingestionActions() {{
  const statusEl = document.getElementById('action-status');

  function visibleActionableRows() {{
    return [...document.querySelectorAll('tbody tr.row')].filter(tr => {{
      if (tr.classList.contains('hidden')) return false;
      const st = tr.dataset.status;
      const ix = tr.dataset.index;
      if (st === 'reject' && (tr.dataset.included || '1') === '1') return true;
      return ['review','error'].includes(st) || ix === 'error';
    }});
  }}

  function namesFromRows(rows) {{
    return rows.map(tr => tr.dataset.name).filter(Boolean);
  }}

  const actionNotes = {{
    mark_not_relevant: 'No relevante: plantilla vacía / solo encabezados Excel',
    mark_verify: 'Verificar: posible foto escaneada o texto manuscrito (OCR)',
  }};

  async function runAction(action, names, note) {{
    if (!names.length) {{
      statusEl.textContent = 'No hay rechazados visibles en el filtro.';
      return;
    }}
    const msg = action === 'mark_not_relevant'
      ? '¿Marcar ' + names.length + ' documento(s) como no relevante y excluir del análisis?'
      : null;
    if (msg && !confirm(msg)) return;
    statusEl.textContent = 'Ejecutando ' + action + ' (' + names.length + ')…';
    try {{
      const r = await fetch('/api/ingestion-action', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          action,
          names,
          note: note || actionNotes[action] || '',
          force: true,
          delete_failed: true,
        }}),
      }});
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || r.statusText);
      const okRows = (data.results || []).filter(row => row.ok);
      if (!okRows.length) {{
        const err = (data.results || []).map(row => row.error).filter(Boolean).join(' · ');
        throw new Error(err || 'Ningún documento procesado');
      }}
      okRows.forEach(row => {{
        const tr = document.querySelector('tr.row[data-name="' + CSS.escape(row.name) + '"]');
        if (!tr) return;
        if (row.new_status === 'excluido') {{
          tr.dataset.status = 'excluido';
          tr.dataset.included = '0';
          const badge = tr.querySelector('td .status');
          if (badge) {{ badge.className = 'status blocked'; badge.textContent = 'Excluido'; }}
          tr.querySelectorAll('.act-group, .rev-link').forEach(el => el.remove());
        }} else if (row.new_status === 'review') {{
          tr.dataset.status = 'review';
          const badge = tr.querySelector('td .status');
          if (badge) {{ badge.className = 'status warn'; badge.textContent = 'Revisar'; }}
        }}
        if (status.value === 'reject' && tr.dataset.status !== 'reject') tr.remove();
      }});
      if (data.summary) {{
        if (data.summary.reject !== undefined) setStat('reject', data.summary.reject);
        if (data.summary.review !== undefined) setStat('review', data.summary.review);
      }}
      function setStat(key, val) {{
        const el = document.querySelector('[data-stat="' + key + '"]');
        if (el && val !== undefined && val !== null) el.textContent = val;
      }}
      statusEl.textContent = 'Listo: ' + okRows.length + '/' + data.total + ' · actualizando…';
      applyFilter();
      setTimeout(() => {{ location.href = location.pathname + '?status=reject&_=' + Date.now(); }}, 800);
    }} catch (e) {{
      statusEl.textContent = 'Error: ' + e.message;
    }}
  }}

  document.getElementById('action-bar').addEventListener('click', ev => {{
    const bulk = ev.target.closest('[data-bulk]');
    if (bulk) {{
      runAction(bulk.dataset.bulk, namesFromRows(visibleActionableRows()), bulk.dataset.note);
      return;
    }}
  }});

  document.querySelector('tbody').addEventListener('click', ev => {{
    const btn = ev.target.closest('button.act');
    if (!btn) return;
    const group = btn.closest('.act-group');
    const name = group && group.dataset.doc;
    if (!name) return;
    runAction(btn.dataset.act, [name], actionNotes[btn.dataset.act]);
  }});
}})();
</script>
</body>
</html>"""
