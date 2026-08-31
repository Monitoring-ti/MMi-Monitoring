"""Reporte de compatibilidad por tipo de archivo en el corpus."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from mmi.ingest.file_types import FILE_TYPES, FileTypeSpec, spec_for_path


def scan_corpus(corpus_root: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not corpus_root.exists():
        return counts
    for path in corpus_root.rglob("*"):
        if path.is_file():
            ext = path.suffix.lower() or "(sin ext)"
            counts[ext] += 1
    return counts


def build_report(corpus_root: Path) -> dict:
    counts = scan_corpus(corpus_root)
    by_extension: list[dict] = []

    seen: set[str] = set()
    for ext, count in counts.most_common():
        seen.add(ext)
        spec = FILE_TYPES.get(ext)
        by_extension.append(_row(ext, count, spec))

    for ext, spec in sorted(FILE_TYPES.items()):
        if ext not in seen and spec.status == "ready":
            by_extension.append(_row(ext, 0, spec))

    ready = sum(1 for r in by_extension if r.get("status") == "ready" and r["count"] > 0)
    planned = sum(r["count"] for r in by_extension if r.get("status") == "planned")
    unsupported = sum(r["count"] for r in by_extension if r.get("status") in {"unsupported", None})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_root": str(corpus_root.resolve()) if corpus_root.exists() else str(corpus_root),
        "total_files": sum(counts.values()),
        "summary": {
            "extensions_found": len(counts),
            "files_ready_pipeline": ready,
            "files_planned": planned,
            "files_unsupported_or_unknown": unsupported,
        },
        "by_extension": by_extension,
        "gaps": [
            g for g in (
                "PPTX: indexación lote 1 pendiente (extracción OK)",
                "Imágenes JPG/PNG: OCR selectivo C4 pendiente",
                ".doc legacy: requiere LibreOffice para conversión",
            )
            if g
        ],
    }


def _row(ext: str, count: int, spec: FileTypeSpec | None) -> dict:
    if spec is None:
        return {
            "extension": ext,
            "count": count,
            "label": ext,
            "status": "unknown",
            "phase0": None,
            "fase0_extract": False,
            "index": False,
            "notes": "Extensión no registrada en file_types.py",
        }
    return {
        "extension": ext,
        "count": count,
        "label": spec.label,
        "status": spec.status,
        "phase0": spec.phase0,
        "fase0_extract": spec.fase0_extract,
        "index": spec.index,
        "chunking": spec.chunking,
        "spec_doc": spec.spec_doc,
        "notes": spec.notes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compatibilidad tipos de archivo vs corpus")
    parser.add_argument("--corpus", type=Path, default=Path("00 DOCUMENTOS NCC30"))
    parser.add_argument("--out", type=Path, default=Path("out/file-types-report.json"))
    args = parser.parse_args(argv)

    report = build_report(args.corpus)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Corpus: {report['corpus_root']}")
    print(f"Archivos: {report['total_files']} · extensiones: {report['summary']['extensions_found']}")
    print()
    print(f"{'Ext':<8} {'N':>4}  {'Estado':<12} Fase0  Index  Notas")
    print("-" * 72)
    for row in report["by_extension"]:
        if row["count"] == 0 and row["status"] not in {"ready", "planned"}:
            continue
        f0 = "sí" if row.get("fase0_extract") else "—"
        ix = "sí" if row.get("index") else "—"
        notes = (row.get("notes") or "")[:40]
        print(
            f"{row['extension']:<8} {row['count']:>4}  "
            f"{row.get('status','?'):<12} {f0:<5}  {ix:<5}  {notes}"
        )
    print(f"\nReporte → {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
