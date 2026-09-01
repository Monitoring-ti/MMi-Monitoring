"""B4 — sincronización catálogo EAM: enrich manifest, seed PG, validar."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from dotenv import load_dotenv

from mmi.catalog.assets import (
    enrich_manifest_asset_tags,
    seed_catalog_from_manifest,
    validate_manifest_catalog,
)


def render_catalog_html(report: dict) -> str:
    s = report.get("summary") or {}
    rows = report.get("issues") or []
    rows_html = "".join(
        f"""<tr class="{escape(r.get('status', ''))}">
  <td>{escape(str(r.get('status')))}</td>
  <td>{escape(str(r.get('asset_tag') or '—'))}</td>
  <td>{escape(str(r.get('modulo') or ''))}</td>
  <td>{escape(str(r.get('name') or ''))}</td>
  <td><small>{escape(str(r.get('relative_path') or '')[:90])}</small></td>
</tr>"""
        for r in rows[:100]
    )
    unknown = ", ".join(escape(t) for t in (report.get("unknown_tags") or [])[:30])
    by_mod = s.get("by_modulo") or {}
    mod_rows = "".join(
        f"<tr><td>{escape(m)}</td><td>{v.get('total',0)}</td>"
        f"<td>{v.get('valid',0)}</td><td>{v.get('unknown',0)}</td><td>{v.get('empty',0)}</td></tr>"
        for m, v in sorted(by_mod.items())
    )
    return f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><title>Catálogo EAM B4</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #0f1419; color: #e6edf3; }}
.stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px; }}
.card b {{ font-size: 1.4rem; display: block; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-top: 12px; }}
th, td {{ border: 1px solid #30363d; padding: 6px 8px; vertical-align: top; }}
th {{ background: #161b22; }}
tr.ok {{ background: rgba(46,160,67,.06); }}
tr.unknown, tr.sin_tag {{ background: rgba(248,81,73,.06); }}
.meta {{ color: #8b949e; }}
a {{ color: #58a6ff; }}
</style></head><body>
<h1>Catálogo EAM — validación B4</h1>
<p class="meta">Generado {escape(str(report.get('generated_at', '')))} · tenant {escape(str(report.get('tenant', '')))}</p>
<div class="stats">
  <div class="card"><b>{s.get('entries_included', 0)}</b> en análisis</div>
  <div class="card"><b>{s.get('with_asset_tag', 0)}</b> con asset_tag</div>
  <div class="card"><b>{s.get('valid_tags', 0)}</b> válidos en catálogo</div>
  <div class="card"><b>{int((s.get('coverage') or 0)*100)}%</b> cobertura</div>
  <div class="card"><b>{s.get('catalog_size', 0)}</b> tags en PG</div>
</div>
<p><a href="review.html">Revisión</a> · <a href="process-manifest.json">Manifest</a></p>
<h2>Por módulo</h2>
<table><thead><tr><th>Módulo</th><th>Total</th><th>Válidos</th><th>Unknown</th><th>Sin tag</th></tr></thead>
<tbody>{mod_rows}</tbody></table>
<h2>Tags desconocidos ({s.get('unknown_tag_count', 0)})</h2>
<p><small>{unknown or '—'}</small></p>
<h2>Incidencias (muestra)</h2>
<table><thead><tr><th>Estado</th><th>Tag</th><th>Módulo</th><th>Archivo</th><th>Ruta</th></tr></thead>
<tbody>{rows_html or '<tr><td colspan="5">Sin incidencias</td></tr>'}</tbody></table>
</body></html>"""


def run_catalog_sync(
    manifest_path: Path,
    *,
    tenant: str = "monitoring",
    enrich: bool = True,
    seed: bool = True,
    dry_run: bool = False,
) -> dict:
    result: dict = {"tenant": tenant, "manifest": str(manifest_path)}
    if enrich:
        changed = enrich_manifest_asset_tags(manifest_path, write=not dry_run)
        result["enriched_fields"] = changed
    if seed:
        inserted = seed_catalog_from_manifest(
            manifest_path, tenant_slug=tenant, dry_run=dry_run
        )
        result["seeded_tags"] = len(inserted)
        result["seed_sample"] = inserted[:20]
    report = validate_manifest_catalog(manifest_path, tenant_slug=tenant)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["validation"] = report
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B4 — catálogo EAM (enrich + seed + validar)")
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-enrich", action="store_true")
    parser.add_argument("--no-seed", action="store_true")
    parser.add_argument("--validate-only", action="store_true", help="Solo validar, sin enrich/seed")
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    manifest = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    out_dir = args.out if args.out.is_absolute() else repo / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.validate_only:
        report = validate_manifest_catalog(manifest, tenant_slug=args.tenant)
        report["generated_at"] = datetime.now(timezone.utc).isoformat()
        payload = {"validation": report}
    else:
        payload = run_catalog_sync(
            manifest,
            tenant=args.tenant,
            enrich=not args.no_enrich,
            seed=not args.no_seed,
            dry_run=args.dry_run,
        )
        report = payload["validation"]

    json_path = out_dir / "catalog-validation.json"
    html_path = out_dir / "catalog-validation.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_catalog_html(report), encoding="utf-8")

    s = report.get("summary") or {}
    label = "Dry-run" if args.dry_run else "B4 sync"
    print(
        f"{label}: {s.get('entries_included', 0)} docs · "
        f"{s.get('with_asset_tag', 0)} con tag · "
        f"{s.get('valid_tags', 0)} válidos ({int((s.get('coverage') or 0)*100)}%) · "
        f"catálogo PG {s.get('catalog_size', 0)}"
    )
    if payload.get("enriched_fields") is not None:
        print(f"  enrich: {payload['enriched_fields']} campos actualizados")
    if payload.get("seeded_tags") is not None:
        print(f"  seed: {payload['seeded_tags']} tags")
    print(f"JSON → {json_path.resolve()}")
    print(f"HTML → {html_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
