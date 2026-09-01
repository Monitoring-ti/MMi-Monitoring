"""C4.13 — Piloto: plan_scan INF TEC → OCR → extract → index."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from dotenv import load_dotenv

from mmi.corpus.paths import DEFAULT_CORPUS, DEFAULT_EXTRACT_FULL
from mmi.index.ocr_sync import sync_ocr_to_extract
from mmi.index.pipeline import ingest_file
from mmi.ingest.plan_detect import detect_plan
from mmi.tools.ocr_worker import run_ocr_job


def _engineering_key(name: str) -> str:
    m = re.search(r"(\d{6,}-\d{5}-\d{3}[A-Z]{2}-\d{5})", name, re.I)
    if m:
        return m.group(1).upper()
    stem = Path(name).stem.replace(" ", "-")[:48]
    return stem


def pick_pilot_plano(corpus_root: Path, *, subdir: str = "02 INF TEC") -> Path | None:
    root = corpus_root / subdir if subdir else corpus_root
    if not root.is_dir():
        root = corpus_root
    best: tuple[float, int, Path] | None = None
    for pdf in sorted(root.rglob("*.pdf")):
        det = detect_plan(pdf)
        if not det.is_plano or det.block_ocr:
            continue
        score = det.confidence - det.page_count * 0.01
        if det.page_count > 12:
            continue
        row = (score, -det.page_count, pdf)
        if best is None or row[0] > best[0]:
            best = row
    return best[2] if best else None


def run_pilot(
    *,
    corpus: Path = DEFAULT_CORPUS,
    extract_root: Path = DEFAULT_EXTRACT_FULL,
    out_root: Path = Path("out"),
    file: Path | None = None,
    document_key: str | None = None,
    activate: bool = True,
) -> dict:
    path = file or pick_pilot_plano(corpus)
    if path is None:
        raise FileNotFoundError("No se encontró plano candidato en corpus")

    doc_key = document_key or _engineering_key(path.name)
    doc_id = doc_key.replace("/", "-")[:60]

    ocr_result = run_ocr_job(
        path,
        document_id=doc_id,
        out_root=out_root,
        document_key=doc_key,
        version_label="vigente",
        tipo="plano",
        skip_existing=False,
        require_plano=True,
    )
    if ocr_result.get("status") == "skipped_not_plano":
        return {"status": "error", "reason": "not_plano", **ocr_result}

    staging = Path(ocr_result["staging"])
    extract_dir = sync_ocr_to_extract(staging, extract_root)

    ingest = ingest_file(
        path,
        tenant_slug="monitoring",
        tipo="plano",
        version_label="vigente",
        document_key=doc_key,
        activate=activate,
        relative_path=str(path.relative_to(corpus)) if path.is_relative_to(corpus) else path.name,
    )

    summary = {
        "status": "completed",
        "pilot_pdf": str(path),
        "document_key": doc_key,
        "ocr": ocr_result,
        "extract_dir": str(extract_dir),
        "index": ingest,
    }
    out_path = out_root / "ocr-pilot-summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="C4.13 piloto OCR plano + indexación")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--extract-dir", type=Path, default=DEFAULT_EXTRACT_FULL)
    parser.add_argument("--file", type=Path, help="PDF plano específico")
    parser.add_argument("--document-key", default="")
    parser.add_argument("--no-activate", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv()
    try:
        result = run_pilot(
            corpus=args.corpus,
            extract_root=args.extract_dir,
            file=args.file,
            document_key=args.document_key or None,
            activate=not args.no_activate,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    estado = (result.get("index") or {}).get("estado", "")
    return 0 if estado in {"active", "indexed", "indexado", "duplicado"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
