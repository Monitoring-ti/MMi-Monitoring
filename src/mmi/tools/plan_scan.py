"""Escanea corpus y lista candidatos a plano vs documento."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mmi.corpus.paths import DEFAULT_CORPUS
from mmi.ingest.plan_detect import detect_plan


def scan_corpus(
    corpus_root: Path,
    *,
    subdir: str | None = None,
    limit: int | None = None,
) -> dict:
    root = corpus_root / subdir if subdir else corpus_root
    if not root.is_dir():
        root = corpus_root
    pdfs = sorted(root.rglob("*.pdf"))
    if limit:
        pdfs = pdfs[:limit]
    planos: list[dict] = []
    documentos: list[dict] = []
    mixtos: list[dict] = []
    errors: list[dict] = []
    for path in pdfs:
        try:
            det = detect_plan(path)
        except Exception as exc:  # noqa: BLE001
            errors.append({"path": str(path), "error": str(exc)[:200]})
            continue
        row = det.to_dict()
        row["name"] = path.name
        try:
            row["relative_path"] = str(path.relative_to(corpus_root))
        except ValueError:
            row["relative_path"] = str(path)
        if det.is_plano:
            planos.append(row)
        elif det.kind == "documento":
            documentos.append(row)
        else:
            mixtos.append(row)
    return {
        "corpus": str(corpus_root),
        "scan_root": str(root),
        "scanned": len(pdfs),
        "planos": len(planos),
        "documentos": len(documentos),
        "mixtos": len(mixtos),
        "plano_candidates": planos,
        "document_samples": documentos[:20],
        "mixto_samples": mixtos[:20],
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detectar planos en corpus PDF")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--subdir", default="", help="Subcarpeta del corpus (ej. 02 INF TEC)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", type=Path, default=Path("out/plan-scan.json"))
    parser.add_argument("--plano-only", action="store_true")
    args = parser.parse_args(argv)

    payload = scan_corpus(args.corpus, subdir=args.subdir or None, limit=args.limit)
    if args.plano_only:
        payload = {
            "corpus": payload["corpus"],
            "scan_root": payload["scan_root"],
            "scanned": payload["scanned"],
            "planos": payload["planos"],
            "plano_candidates": payload["plano_candidates"],
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Escaneados: {payload['scanned']} PDFs")
    if args.plano_only:
        print(f"  Planos: {payload['planos']}")
    else:
        print(f"  Planos: {payload['planos']} · Documentos: {payload['documentos']} · Mixtos: {payload['mixtos']}")
    if payload.get("errors"):
        print(f"  Errores: {len(payload['errors'])} PDFs corruptos/ilegibles")
    print(f"→ {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
