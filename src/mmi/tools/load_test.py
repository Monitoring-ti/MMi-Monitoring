"""Prueba de carga: búsqueda, API HTTP y extracción Fase 0."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

from mmi.analysis.load_metrics import summarize_latencies
from mmi.analysis.load_report import build_report, write_load_report

DEFAULT_QUERIES = [
    "SGP-07MYC-GUIGS-00001 mantenibilidad confiabilidad",
    "procedimiento FMECA análisis de modos de falla",
    "RCM mantenimiento basado en confiabilidad",
    "NCC-030 requisitos proyecto inversión",
    "IFC-078 activo fijo registro contable",
    "check list mantenibilidad cumplimiento",
    "SGPD-07MYC-PROGS-0001 procedimiento estudios",
    "taller capacitación FMECA Monitoring",
    "criticidad equipo mantenimiento",
    "ISO 14224 confiabilidad datos",
]


def _load_queries(path: Path | None) -> list[str]:
    if path is None:
        return list(DEFAULT_QUERIES)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [str(q).strip() for q in data if str(q).strip()]
    if isinstance(data, dict) and isinstance(data.get("queries"), list):
        return [str(q).strip() for q in data["queries"] if str(q).strip()]
    raise ValueError("queries file debe ser lista JSON o {\"queries\": [...]}")


def _cycle_queries(queries: list[str], n: int) -> list[str]:
    if not queries:
        raise ValueError("Lista de consultas vacía")
    return [queries[i % len(queries)] for i in range(n)]


def _index_snapshot(tenant: str) -> dict:
    try:
        from mmi.index.store import pg_count_chunks, pg_get_tenant_id, pg_list_documents

        tid = pg_get_tenant_id(tenant)
        docs = pg_list_documents(tid)
        chunks = sum(pg_count_chunks(d["id"]) for d in docs)
        return {"tenant": tenant, "documents": len(docs), "chunks": chunks}
    except Exception as exc:  # noqa: BLE001
        return {"tenant": tenant, "error": str(exc)[:200]}


def _run_search_direct(engine, query: str, limit: int) -> tuple[float, str | None]:
    t0 = time.perf_counter()
    try:
        hits = engine.search(query, limit=limit)
        ms = (time.perf_counter() - t0) * 1000
        if not hits:
            return ms, None
        return ms, None
    except Exception as exc:  # noqa: BLE001
        return -1.0, str(exc)[:300]


def _run_search_http(base_url: str, query: str, limit: int) -> tuple[float, str | None]:
    payload = json.dumps({"query": query, "limit": limit}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp.read()
        return (time.perf_counter() - t0) * 1000, None
    except Exception as exc:  # noqa: BLE001
        return -1.0, str(exc)[:300]


def _run_ask_http(base_url: str, query: str, limit: int) -> tuple[float, str | None]:
    payload = json.dumps({"query": query, "limit": limit}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/ask",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            resp.read()
        return (time.perf_counter() - t0) * 1000, None
    except Exception as exc:  # noqa: BLE001
        return -1.0, str(exc)[:300]


def _run_extract(manifest_path: Path, extract_root: Path) -> tuple[float, str | None]:
    from mmi.index.blocks import blocks_from_path
    from mmi.index.chunking import chunk_blocks

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files") or []
    if not files:
        return -1.0, "manifest sin archivos"

    entry = next(
        (e for e in files if e.get("absolute_path") and Path(e["absolute_path"]).exists()),
        None,
    )
    if entry is None:
        return -1.0, "ningún archivo del manifest existe en disco"

    path = Path(entry["absolute_path"])
    fmt = path.suffix.lower()
    t0 = time.perf_counter()
    try:
        blocks = blocks_from_path(
            path,
            document_key=entry.get("document_key") or entry.get("name", ""),
            version_label=entry.get("revision") or "",
            tipo=entry.get("suggested_tipo", "otro"),
        )
        chunk_blocks(blocks, fmt, entry.get("suggested_tipo", "otro"))
        return (time.perf_counter() - t0) * 1000, None
    except Exception as exc:  # noqa: BLE001
        return -1.0, str(exc)[:300]


def _execute_scenario(
    name: str,
    target: str,
    queries: list[str],
    *,
    concurrency: int,
    worker,
) -> dict:
    latencies: list[float] = []
    sample_errors: list[dict] = []
    wall0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {pool.submit(worker, q): q for q in queries}
        for fut in as_completed(futures):
            q = futures[fut]
            try:
                ms, err = fut.result()
            except Exception as exc:  # noqa: BLE001
                ms, err = -1.0, str(exc)[:300]
            latencies.append(ms)
            if err and len(sample_errors) < 10:
                sample_errors.append({"query": q, "error": err})

    wall_ms = (time.perf_counter() - wall0) * 1000
    stats = summarize_latencies(latencies, wall_ms=wall_ms)
    return {
        "name": name,
        "target": target,
        "stats": stats.to_dict(),
        "sample_errors": sample_errors,
    }


def run_load_test(
    *,
    tenant: str,
    requests: int,
    concurrency: int,
    limit: int,
    queries: list[str],
    base_url: str,
    manifest_path: Path | None,
    include_http: bool,
    include_ask: bool,
    include_extract: bool,
) -> list[dict]:
    from mmi.search.engine import HybridSearchEngine

    workload = _cycle_queries(queries, requests)
    scenarios: list[dict] = []

    engine = HybridSearchEngine(tenant_slug=tenant)
    scenarios.append(
        _execute_scenario(
            "search-direct",
            "HybridSearchEngine",
            workload,
            concurrency=concurrency,
            worker=lambda q: _run_search_direct(engine, q, limit),
        )
    )

    if include_http:
        scenarios.append(
            _execute_scenario(
                "search-http",
                base_url,
                workload,
                concurrency=concurrency,
                worker=lambda q: _run_search_http(base_url, q, limit),
            )
        )
        if include_ask:
            ask_n = min(requests, max(3, requests // 4))
            ask_workload = _cycle_queries(queries, ask_n)
            scenarios.append(
                _execute_scenario(
                    "ask-http",
                    base_url,
                    ask_workload,
                    concurrency=max(1, min(concurrency, 2)),
                    worker=lambda q: _run_ask_http(base_url, q, limit),
                )
            )

    if include_extract and manifest_path and manifest_path.exists():
        extract_workload = _cycle_queries(queries, min(requests, 10))
        extract_root = Path("out/lote1-extract")
        scenarios.append(
            _execute_scenario(
                "extract-chunk",
                str(manifest_path.name),
                extract_workload,
                concurrency=1,
                worker=lambda _q: _run_extract(manifest_path, extract_root),
            )
        )

    return scenarios


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prueba de carga MMI (búsqueda + reporte)")
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--requests", type=int, default=30, help="Requests por escenario")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--limit", type=int, default=6, help="Top-K búsqueda")
    parser.add_argument("--queries-file", type=Path, help="JSON con lista de consultas")
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8773")
    parser.add_argument("--http", action="store_true", help="Incluir escenario POST /api/search")
    parser.add_argument("--ask", action="store_true", help="Incluir escenario POST /api/ask (OpenRouter)")
    parser.add_argument("--extract", action="store_true", help="Incluir extracción+chunk 1er doc manifest")
    parser.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    queries_path = args.queries_file
    if queries_path and not queries_path.is_absolute():
        queries_path = repo / queries_path
    manifest = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    out_dir = args.out if args.out.is_absolute() else repo / args.out

    queries = _load_queries(queries_path)
    notes: list[str] = []
    if args.ask:
        notes.append("Escenario ask-http consume OpenRouter; concurrencia limitada a 2.")
    if args.http or args.ask:
        notes.append(f"Requiere serve_local activo en {args.base_url}")

    print(f"Prueba de carga · {args.requests} req × concurrencia {args.concurrency}")
    print(f"Consultas base: {len(queries)}")

    scenarios = run_load_test(
        tenant=args.tenant,
        requests=args.requests,
        concurrency=args.concurrency,
        limit=args.limit,
        queries=queries,
        base_url=args.base_url,
        manifest_path=manifest,
        include_http=args.http,
        include_ask=args.ask,
        include_extract=args.extract,
    )

    report = build_report(
        scenarios=scenarios,
        index_snapshot=_index_snapshot(args.tenant),
        config={
            "tenant": args.tenant,
            "requests_per_scenario": args.requests,
            "concurrency": args.concurrency,
            "search_limit": args.limit,
            "base_url": args.base_url,
            "queries_count": len(queries),
        },
        notes=notes,
    )

    json_path, html_path = write_load_report(report, out_dir)

    print()
    for sc in scenarios:
        st = sc["stats"]
        print(
            f"  {sc['name']:<16} p50={st['p50_ms']:>6.0f} ms  "
            f"p95={st['p95_ms']:>6.0f} ms  err={st['errors']}  rps={st['rps']:.2f}"
        )
    print(f"\nJSON   → {json_path.resolve()}")
    print(f"Reporte → {html_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
