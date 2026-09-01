"""Reporte JSON + HTML de pruebas de carga MMI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


def build_report(
    *,
    scenarios: list[dict[str, Any]],
    index_snapshot: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": config or {},
        "index_snapshot": index_snapshot or {},
        "scenarios": scenarios,
        "notes": notes or [],
    }


def render_load_report_html(report: dict[str, Any]) -> str:
    cfg = report.get("config") or {}
    snap = report.get("index_snapshot") or {}
    scenarios = report.get("scenarios") or []
    notes = report.get("notes") or []

    scenario_rows = ""
    for sc in scenarios:
        stats = sc.get("stats") or {}
        scenario_rows += f"""
        <tr>
          <td>{escape(str(sc.get("name", "")))}</td>
          <td>{escape(str(sc.get("target", "")))}</td>
          <td class="num">{stats.get("count", 0)}</td>
          <td class="num">{stats.get("ok", 0)}</td>
          <td class="num">{stats.get("errors", 0)}</td>
          <td class="num">{stats.get("p50_ms", "—")}</td>
          <td class="num">{stats.get("p95_ms", "—")}</td>
          <td class="num">{stats.get("p99_ms", "—")}</td>
          <td class="num">{stats.get("mean_ms", "—")}</td>
          <td class="num">{stats.get("rps", "—")}</td>
        </tr>"""

    error_rows = ""
    for sc in scenarios:
        for err in sc.get("sample_errors") or []:
            error_rows += f"""
        <tr>
          <td>{escape(str(sc.get("name", "")))}</td>
          <td>{escape(str(err.get("query", ""))[:80])}</td>
          <td>{escape(str(err.get("error", ""))[:200])}</td>
        </tr>"""

    notes_html = "".join(f"<li>{escape(n)}</li>" for n in notes)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MMI — Reporte de carga</title>
<style>
  :root {{ font-family: system-ui, Segoe UI, sans-serif; color: #1a1a1a; }}
  body {{ margin: 0; padding: 1.5rem 2rem; background: #f4f6f8; }}
  h1 {{ margin: 0 0 .25rem; font-size: 1.4rem; }}
  .meta {{ color: #555; margin-bottom: 1.25rem; font-size: .9rem; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: .75rem; margin-bottom: 1.25rem; }}
  .card {{ background: #fff; border: 1px solid #dde3ea; border-radius: 8px; padding: .75rem 1rem; min-width: 140px; }}
  .card b {{ display: block; font-size: 1.35rem; }}
  .card span {{ color: #666; font-size: .8rem; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #dde3ea; border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: .55rem .65rem; text-align: left; border-bottom: 1px solid #eef2f6; font-size: .88rem; }}
  th {{ background: #eef3f8; font-weight: 600; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  section {{ margin-bottom: 1.5rem; }}
  h2 {{ font-size: 1.05rem; margin: 0 0 .5rem; }}
  ul {{ margin: .25rem 0; padding-left: 1.2rem; color: #444; }}
  .ok {{ color: #0a7; }}
  .warn {{ color: #b60; }}
</style>
</head>
<body>
  <h1>Reporte de prueba de carga — MMi</h1>
  <p class="meta">Generado: {escape(str(report.get("generated_at", "")))} · Tenant: {escape(str(cfg.get("tenant", "monitoring")))}</p>

  <div class="cards">
    <div class="card"><b>{snap.get("documents", "—")}</b><span>Documentos indexados</span></div>
    <div class="card"><b>{snap.get("chunks", "—")}</b><span>Chunks totales</span></div>
    <div class="card"><b>{cfg.get("concurrency", "—")}</b><span>Concurrencia</span></div>
    <div class="card"><b>{cfg.get("requests_per_scenario", "—")}</b><span>Requests / escenario</span></div>
  </div>

  <section>
    <h2>Resultados por escenario</h2>
    <table>
      <thead>
        <tr>
          <th>Escenario</th><th>Target</th><th>N</th><th>OK</th><th>Err</th>
          <th>p50 ms</th><th>p95 ms</th><th>p99 ms</th><th>Media ms</th><th>RPS</th>
        </tr>
      </thead>
      <tbody>{scenario_rows or '<tr><td colspan="10">Sin datos</td></tr>'}</tbody>
    </table>
  </section>

  <section>
    <h2>Errores (muestra)</h2>
    <table>
      <thead><tr><th>Escenario</th><th>Consulta</th><th>Error</th></tr></thead>
      <tbody>{error_rows or '<tr><td colspan="3" class="ok">Sin errores</td></tr>'}</tbody>
    </table>
  </section>

  {"<section><h2>Notas</h2><ul>" + notes_html + "</ul></section>" if notes_html else ""}

  <p class="meta">JSON: <code>out/load-test-report.json</code> · CLI: <code>python -m mmi.tools.load_test</code></p>
</body>
</html>"""


def write_load_report(report: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "load-test-report.json"
    html_path = out_dir / "load-test-report.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_load_report_html(report), encoding="utf-8")
    return json_path, html_path
