"""CLI: clasificar archivos del manifest (dup físico / versión / nuevo / revisión)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from mmi.catalog.version_detect import (
    load_registry_from_supabase,
    scan_manifest,
    summarize_decisions,
)
from mmi.corpus.paths import DEFAULT_EXTRACT_FULL


def _print_summary(stats: dict[str, int]) -> None:
    print("\n--- Resumen ---")
    for key in (
        "total",
        "duplicado_fisico",
        "mismo_contenido",
        "nueva_version",
        "nuevo_documento",
        "needs_review",
        "indexar",
    ):
        if key in stats:
            print(f"  {key}: {stats[key]}")


def _print_samples(decisions, *, kind: str, limit: int = 5) -> None:
    hits = [d for d in decisions if d.kind == kind]
    if not hits:
        return
    print(f"\n--- {kind} (max {limit}) ---")
    for d in hits[:limit]:
        short_hash = d.file_hash[:12] if d.file_hash else "?"
        print(f"  {d.name}")
        print(f"    logical_key: {d.logical_key}")
        print(f"    file_hash: {short_hash}…  reason: {d.reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detectar duplicados físicos vs revisiones vs identidad dudosa (B1 dry-run)",
    )
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--extract-dir", type=Path, default=DEFAULT_EXTRACT_FULL)
    parser.add_argument("--tenant", default="monitoring")
    parser.add_argument("--limit", type=int, help="Máximo de archivos a evaluar")
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Simular registro en memoria sin escribir en índice (default: true)",
    )
    parser.add_argument(
        "--no-supabase",
        action="store_true",
        help="No cargar estado previo desde Supabase",
    )
    parser.add_argument("--json-out", type=Path, default=Path("out/version-detect-summary.json"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv()
    if not args.manifest.exists():
        print(f"Manifest no encontrado: {args.manifest}")
        return 1

    registry = None
    if not args.no_supabase:
        registry = load_registry_from_supabase(args.tenant)
        n_pg = len(registry.by_file_hash)
        if n_pg:
            print(f"Registro Supabase: {n_pg} file_hash conocidos")

    decisions = scan_manifest(
        args.manifest,
        extract_root=args.extract_dir if args.extract_dir.exists() else None,
        tenant_slug=args.tenant,
        registry=registry,
        limit=args.limit,
        simulate=args.dry_run,
    )
    stats = summarize_decisions(decisions)

    print(f"Manifest: {args.manifest}")
    print(f"Archivos evaluados: {stats['total']}")
    _print_summary(stats)
    _print_samples(decisions, kind="duplicado_fisico")
    _print_samples(decisions, kind="nueva_version")
    _print_samples(decisions, kind="needs_review")

    if args.verbose:
        print("\n--- Detalle ---")
        for d in decisions:
            print(json.dumps(d.to_dict(), ensure_ascii=False))

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(args.manifest),
        "tenant": args.tenant,
        "stats": stats,
        "decisions": [d.to_dict() for d in decisions],
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
