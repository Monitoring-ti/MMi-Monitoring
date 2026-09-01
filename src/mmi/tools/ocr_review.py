"""UI revisión OCR — diff crudo vs normalizado (C4.12)."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from mmi.ingest.ocr_models import OcrResult
from mmi.ingest.ocr_validate import OcrValidation


def _esc(value: Any) -> str:
    return escape(str(value) if value is not None else "")


def render_ocr_review_html(
    ocr: OcrResult,
    validations: list[OcrValidation],
    *,
    manifest: dict[str, Any] | None = None,
    only_flagged: bool = True,
) -> str:
    manifest = manifest or {}
    val_by_page: dict[int, list[OcrValidation]] = {}
    for row in validations:
        if row.page_number is not None:
            val_by_page.setdefault(row.page_number, []).append(row)

    flagged_pages = {
        v.page_number for v in validations if v.status in {"review", "reject"} and v.page_number
    }

    page_sections: list[str] = []
    for page in ocr.pages:
        if only_flagged and flagged_pages and page.page_number not in flagged_pages:
            continue
        conf = f"{page.confidence:.0%}" if page.confidence is not None else "?"
        blocks_html: list[str] = []
        for block in page.blocks:
            raw = block.text_raw or ""
            norm = block.text_normalized or raw
            changed = raw != norm
            if only_flagged and not changed and page.page_number not in flagged_pages:
                continue
            bconf = f"{block.confidence:.0%}" if block.confidence is not None else "?"
            blocks_html.append(
                f"""
  <div class="block {'changed' if changed else ''}">
    <div class="block-head">
      <span class="badge">{_esc(block.block_type)}</span>
      <span class="badge">b{block.block_index}</span>
      <span class="badge">conf {bconf}</span>
    </div>
    <div class="diff-grid">
      <div class="col">
        <div class="label">Crudo</div>
        <pre>{_esc(raw) or '—'}</pre>
      </div>
      <div class="col">
        <div class="label">Normalizado</div>
        <pre>{_esc(norm) or '—'}</pre>
      </div>
    </div>
  </div>"""
            )
        if not blocks_html and not only_flagged and (page.text_raw or page.text_normalized):
            blocks_html.append(
                f"""
  <div class="block">
    <div class="diff-grid">
      <div class="col"><div class="label">Crudo</div><pre>{_esc(page.text_raw)}</pre></div>
      <div class="col"><div class="label">Normalizado</div><pre>{_esc(page.text_normalized)}</pre></div>
    </div>
  </div>"""
            )

        page_vals = val_by_page.get(page.page_number, [])
        val_html = ""
        if page_vals:
            items = "".join(
                f'<li class="{_esc(v.status)}"><b>{_esc(v.rule)}</b> — {_esc(v.field_name or "")} '
                f'{_esc(v.raw_value or "")}</li>'
                for v in page_vals[:12]
            )
            val_html = f'<ul class="validations">{items}</ul>'

        if not blocks_html:
            continue

        page_sections.append(
            f"""
<section class="page">
  <h2>Página {page.page_number} <span class="muted">conf {conf} · {page.status}</span></h2>
  {val_html}
  {''.join(blocks_html)}
</section>"""
        )

    if not page_sections and only_flagged:
        page_sections.append(
            '<p class="meta">Sin páginas con alertas de validación. '
            "Ver JSON completo en staging.</p>"
        )

    val_summary = {"pass": 0, "review": 0, "reject": 0}
    for v in validations:
        val_summary[v.status] = val_summary.get(v.status, 0) + 1

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>OCR Review — {escape(Path(ocr.source_path).name)}</title>
<style>
  :root {{ font-family: Segoe UI, system-ui, sans-serif; background: #141414; color: #e8e8e8; }}
  body {{ margin: 0; padding: 20px 24px 48px; max-width: 1100px; }}
  h1 {{ font-size: 1.2rem; margin: 0 0 8px; }}
  .meta {{ color: #9a9a9a; font-size: 0.88rem; margin-bottom: 18px; line-height: 1.5; }}
  .summary {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }}
  .pill {{ padding: 6px 12px; border-radius: 999px; background: #222; font-size: 0.82rem; }}
  .pill.warn {{ background: #3a2a10; color: #f0d080; }}
  .pill.bad {{ background: #3a1515; color: #f0a0a0; }}
  .pill.ok {{ background: #153a20; color: #8fddb0; }}
  .page {{ border: 1px solid #333; border-radius: 12px; padding: 16px; margin-bottom: 16px; background: #1c1c1c; }}
  .page h2 {{ margin: 0 0 12px; font-size: 1rem; }}
  .muted {{ color: #8a8a8a; font-weight: 400; }}
  .block {{ border: 1px solid #2a2a2a; border-radius: 8px; padding: 12px; margin-top: 10px; background: #181818; }}
  .block.changed {{ border-color: #5a4a18; }}
  .block-head {{ margin-bottom: 8px; }}
  .badge {{ font-size: 0.72rem; padding: 2px 8px; border-radius: 999px; background: #2a2a2a; margin-right: 6px; }}
  .diff-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  @media (max-width: 800px) {{ .diff-grid {{ grid-template-columns: 1fr; }} }}
  .label {{ font-size: 0.72rem; text-transform: uppercase; color: #8ab4ff; margin-bottom: 4px; }}
  pre {{ margin: 0; white-space: pre-wrap; font-size: 0.84rem; line-height: 1.45; color: #d0d0d0; }}
  .validations {{ margin: 0 0 10px; padding-left: 18px; font-size: 0.82rem; color: #c8c8c8; }}
  .validations .review {{ color: #f0d080; }}
  .validations .reject {{ color: #f0a0a0; }}
</style>
</head>
<body>
  <h1>Revisión OCR — {_esc(Path(ocr.source_path).name)}</h1>
  <p class="meta">
    Motor: {_esc(ocr.engine)} · modelo {_esc(ocr.model_id)} ·
    calidad <b>{_esc(ocr.quality)}</b> ·
    {ocr.page_count} páginas
  </p>
  <div class="summary">
    <span class="pill ok">pass {val_summary.get('pass', 0)}</span>
    <span class="pill warn">review {val_summary.get('review', 0)}</span>
    <span class="pill bad">reject {val_summary.get('reject', 0)}</span>
    <span class="pill">hash {_esc(manifest.get('ocr_content_hash', '')[:12])}…</span>
  </div>
  {''.join(page_sections)}
</body>
</html>"""


def write_ocr_review_html(
    staging_path: Path,
    ocr: OcrResult,
    validations: list[OcrValidation],
) -> Path:
    manifest = {}
    manifest_path = staging_path / "manifest.json"
    if manifest_path.exists():
        import json

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out = staging_path / "ocr-review.html"
    out.write_text(render_ocr_review_html(ocr, validations, manifest=manifest), encoding="utf-8")
    return out
