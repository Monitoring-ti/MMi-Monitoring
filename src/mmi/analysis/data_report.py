"""Agregación de métricas corpus / indexación / recuperación (Fase D)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _folder_key(relative_path: str) -> str:
    parts = relative_path.replace("\\", "/").split("/")
    if len(parts) >= 2 and parts[0] == "ODS1 TORR ENF DCH":
        return parts[1] if len(parts) > 1 else parts[0]
    return parts[0] if parts else "?"


def _phase0_by_extension(analyses: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for row in analyses:
        ext = (row.get("extension") or "").lower().lstrip(".") or "otro"
        status = row.get("status") or "unknown"
        out[ext][status] += 1
    return {ext: dict(counts) for ext, counts in out.items()}


def _status_by_tipo(analyses: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for row in analyses:
        tipo = row.get("tipo") or "otro"
        status = row.get("status") or "unknown"
        out[tipo][status] += 1
    return {tipo: dict(counts) for tipo, counts in out.items()}


def _coverage_by_folder(analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in analyses:
        if not row.get("included_in_analysis", True):
            continue
        folder = _folder_key(row.get("relative_path") or "")
        buckets[folder]["total"] += 1
        st = row.get("status") or ""
        buckets[folder][st] += 1
        if row.get("index_status") in {"active", "indexed", "indexado"}:
            buckets[folder]["indexados"] += 1
    rows = []
    for folder, counts in sorted(buckets.items(), key=lambda x: -x[1]["total"]):
        total = counts["total"]
        idx = counts.get("indexados", 0)
        rows.append(
            {
                "folder": folder,
                "total": total,
                "pass": counts.get("pass", 0),
                "reject": counts.get("reject", 0),
                "review": counts.get("review", 0),
                "indexados": idx,
                "index_pct": round(100 * idx / total, 1) if total else 0.0,
            }
        )
    return rows


def _reject_reasons(analyses: list[dict[str, Any]], *, limit: int = 15) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    for row in analyses:
        if row.get("status") != "reject":
            continue
        notes = row.get("notes") or []
        reason = notes[0] if notes else row.get("status_detail") or "sin nota"
        reason = str(reason)[:120]
        counter[reason] += 1
        if len(samples[reason]) < 3:
            samples[reason].append(row.get("name") or "")
    return [
        {"reason": reason, "count": count, "samples": samples[reason]}
        for reason, count in counter.most_common(limit)
    ]


def _planos_by_subdir(plan_scan: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not plan_scan:
        return []
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in plan_scan.get("plano_candidates") or []:
        rel = row.get("relative_path") or ""
        parts = rel.replace("\\", "/").split("/")
        sub = parts[0] if parts else "?"
        buckets[sub].append(row)
    out = []
    for sub, items in sorted(buckets.items(), key=lambda x: -len(x[1])):
        confs = [float(i.get("confidence") or 0) for i in items]
        pages = [int(i.get("page_count") or 0) for i in items]
        out.append(
            {
                "subdir": sub,
                "planos": len(items),
                "avg_confidence": round(sum(confs) / len(confs), 3) if confs else 0,
                "avg_pages": round(sum(pages) / len(pages), 1) if pages else 0,
                "top": sorted(items, key=lambda r: -(r.get("confidence") or 0))[:3],
            }
        )
    return out


def _golden_weak_cases(golden_eval: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not golden_eval:
        return []
    weak = []
    for case in golden_eval.get("cases") or []:
        recall5 = (case.get("metrics") or {}).get("recall@5")
        if recall5 is not None and recall5 < 1.0:
            weak.append(
                {
                    "id": case.get("id"),
                    "category": case.get("category"),
                    "query": case.get("query"),
                    "recall@5": recall5,
                    "mrr": (case.get("metrics") or {}).get("mrr"),
                }
            )
    return weak


def _recommendations(report: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    summary = report.get("corpus_summary") or {}
    if summary.get("reject", 0) > 40:
        recs.append(f"Revisar {summary.get('reject')} documentos reject (ver reject_top).")
    planos = (report.get("planos") or {}).get("total", 0)
    if planos:
        recs.append(f"Escalar OCR: {planos} planos en INF TEC — priorizar subcarpetas con mayor confianza.")
    weak = report.get("golden_weak_cases") or []
    if weak:
        recs.append(f"Golden set: {len(weak)} consultas con recall@5 < 1 — revisar chunking/títulos.")
    coverage = report.get("coverage_by_folder") or []
    low = [c for c in coverage if c.get("index_pct", 100) < 70 and c.get("total", 0) > 20]
    if low:
        names = ", ".join(c["folder"] for c in low[:3])
        recs.append(f"Cobertura indexación baja en: {names}.")
    if not recs:
        recs.append("Corpus estable: mantener smoke test y validación RAG en CI.")
    return recs


def build_data_report(out_dir: Path) -> dict[str, Any]:
    out_dir = Path(out_dir)
    status = _load_json(out_dir / "analysis-status.json") or {}
    analyses = status.get("analyses") or []
    if isinstance(analyses, dict):
        analyses = list(analyses.values())

    plan_scan = _load_json(out_dir / "plan-scan.json")
    golden = _load_json(out_dir / "golden-set-eval.json")
    smoke = _load_json(out_dir / "query-smoke.json")
    rag_val = _load_json(out_dir / "rag-validation.json")
    index_sum = _load_json(out_dir / "index-corpus-summary.json")

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "analysis_status": (out_dir / "analysis-status.json").exists(),
            "plan_scan": (out_dir / "plan-scan.json").exists(),
            "golden_set_eval": (out_dir / "golden-set-eval.json").exists(),
            "query_smoke": (out_dir / "query-smoke.json").exists(),
            "rag_validation": (out_dir / "rag-validation.json").exists(),
            "index_corpus_summary": (out_dir / "index-corpus-summary.json").exists(),
        },
        "corpus_summary": status.get("summary") or {},
        "index_summary": status.get("index_summary") or (index_sum or {}),
        "token_summary": status.get("token_summary") or {},
        "phase0_by_extension": _phase0_by_extension(analyses),
        "status_by_tipo": _status_by_tipo(analyses),
        "coverage_by_folder": _coverage_by_folder(analyses),
        "reject_top": _reject_reasons(analyses),
        "planos": {
            "total": (plan_scan or {}).get("planos", 0),
            "scanned": (plan_scan or {}).get("scanned", 0),
            "by_subdir": _planos_by_subdir(plan_scan if isinstance(plan_scan, dict) else None),
        },
        "retrieval": {
            "golden": (golden or {}).get("summary") if isinstance(golden, dict) else None,
            "golden_by_category": (golden or {}).get("summary", {}).get("by_category")
            if isinstance(golden, dict)
            else None,
            "smoke": (smoke or {}).get("summary") if isinstance(smoke, dict) else None,
            "rag_validation": (rag_val or {}).get("summary") if isinstance(rag_val, dict) else None,
        },
        "golden_weak_cases": _golden_weak_cases(golden if isinstance(golden, dict) else None),
    }
    report["recommendations"] = _recommendations(report)
    return report


def render_data_report_html(report: dict[str, Any]) -> str:
    cs = report.get("corpus_summary") or {}
    idx = report.get("index_summary") or {}
    ret = report.get("retrieval") or {}
    golden = ret.get("golden") or {}

    folder_rows = "".join(
        f"<tr><td>{r['folder']}</td><td>{r['total']}</td><td>{r['pass']}</td>"
        f"<td>{r['indexados']}</td><td>{r['index_pct']}%</td></tr>"
        for r in (report.get("coverage_by_folder") or [])[:12]
    )
    reject_rows = "".join(
        f"<tr><td>{r['count']}</td><td>{r['reason']}</td></tr>"
        for r in (report.get("reject_top") or [])[:10]
    )
    plano_rows = "".join(
        f"<tr><td>{p['subdir']}</td><td>{p['planos']}</td>"
        f"<td>{p['avg_confidence']}</td><td>{p['avg_pages']}</td></tr>"
        for p in (report.get("planos") or {}).get("by_subdir") or []
    )
    recs = "".join(f"<li>{r}</li>" for r in (report.get("recommendations") or []))

    return f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><title>Análisis de datos MMI</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #0f1419; color: #e6edf3; }}
h1 {{ font-size: 1.4rem; }}
.meta {{ color: #8b949e; margin-bottom: 20px; }}
.stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; min-width: 120px; }}
.card b {{ display: block; font-size: 1.4rem; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 0.85rem; }}
th, td {{ border: 1px solid #30363d; padding: 8px; text-align: left; }}
th {{ background: #161b22; }}
a {{ color: #58a6ff; }}
ul {{ line-height: 1.6; }}
</style></head><body>
<h1>Análisis de datos — ODS1/NCC30</h1>
<p class="meta">Generado: {report.get('generated_at', '')} · Fase D</p>
<div class="stats">
  <div class="card"><span>Fase 0 pass</span><b>{cs.get('pass', '—')}</b></div>
  <div class="card"><span>Reject</span><b>{cs.get('reject', '—')}</b></div>
  <div class="card"><span>Indexados</span><b>{cs.get('indexados', idx.get('indexados', '—'))}</b></div>
  <div class="card"><span>Chunks</span><b>{idx.get('chunks', '—')}</b></div>
  <div class="card"><span>Golden MRR</span><b>{golden.get('mrr', '—')}</b></div>
  <div class="card"><span>Planos INF TEC</span><b>{(report.get('planos') or {}).get('total', '—')}</b></div>
</div>
<h2>Cobertura por carpeta</h2>
<table><thead><tr><th>Carpeta</th><th>Total</th><th>Pass</th><th>Index</th><th>%</th></tr></thead>
<tbody>{folder_rows or '<tr><td colspan="5">Sin datos</td></tr>'}</tbody></table>
<h2>Rechazos top</h2>
<table><thead><tr><th>#</th><th>Motivo</th></tr></thead>
<tbody>{reject_rows or '<tr><td colspan="2">Sin rejects</td></tr>'}</tbody></table>
<h2>Planos por subcarpeta (INF TEC)</h2>
<table><thead><tr><th>Subcarpeta</th><th>Planos</th><th>Conf. media</th><th>Págs media</th></tr></thead>
<tbody>{plano_rows or '<tr><td colspan="4">Sin plan-scan.json</td></tr>'}</tbody></table>
<h2>Recomendaciones</h2>
<ul>{recs}</ul>
<p class="meta"><a href="data-analysis/report.json">report.json</a> ·
<a href="../review.html">Revisión</a> · <a href="../mapa.html">Mapa</a></p>
</body></html>"""
