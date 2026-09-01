"""Worker OCR reanudable por página (C4.11)."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from mmi.config import get_ocr_settings
from mmi.corpus.lote1 import resolve_lote1
from mmi.corpus.paths import DEFAULT_CORPUS
from mmi.index.chunking import file_sha256
from mmi.index.ocr_chunking import chunk_ocr_pages
from mmi.index.ocr_store import load_ocr_staging, page_already_processed, save_ocr_staging, staging_dir
from mmi.ingest.ocr import extract_with_ocr
from mmi.ingest.plan_detect import detect_plan
from mmi.ingest.ocr_models import OcrBlock, OcrPage, OcrResult
from mmi.ingest.ocr_validate import validate_ocr_result, validations_summary
from mmi.tools.ocr_review import write_ocr_review_html


def run_ocr_job(
    path: Path,
    *,
    document_id: str,
    out_root: Path = Path("out"),
    document_key: str = "",
    version_label: str = "",
    tipo: str = "plano",
    skip_existing: bool = True,
    require_plano: bool = True,
) -> dict:
    """Ejecuta OCR, valida, persiste staging y genera chunks + HTML revisión."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    file_hash = file_sha256(path)
    root = staging_dir(out_root, document_id)

    detection = detect_plan(path)
    if require_plano and (detection.block_ocr or not detection.is_plano):
        return {
            "status": "skipped_not_plano",
            "document_id": document_id,
            "source": str(path),
            "detection": detection.to_dict(),
            "message": detection.block_reason or "No clasificado como plano",
        }

    if skip_existing:
        existing = load_ocr_staging(root)
        if existing and existing.get("file_hash") == file_hash and existing.get("pages_data"):
            return {
                "status": "skipped",
                "document_id": document_id,
                "staging": str(root),
                "quality": existing.get("quality"),
                "page_count": existing.get("page_count"),
            }

    ocr_result = extract_with_ocr(
        path, file_hash=file_hash, validate=True, document_key=document_key or document_id
    )
    ocr = _ocr_from_extracted(ocr_result, file_hash=file_hash)
    validations, quality = validate_ocr_result(ocr)
    ocr.quality = quality

    staging_path = save_ocr_staging(ocr, document_id, out_root, validations=validations)
    chunks = chunk_ocr_pages(
        ocr.pages,
        document_name=path.name,
        document_key=document_key or document_id,
        version_label=version_label,
        tipo=detection.suggested_tipo if detection.is_plano else tipo,
    )
    chunks_path = staging_path / "chunks.json"
    chunks_path.write_text(
        json.dumps([asdict(c) for c in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    review_path = write_ocr_review_html(staging_path, ocr, validations)

    for page in ocr.pages:
        if page_already_processed(staging_path, page.page_number, page.page_hash):
            continue

    return {
        "status": "completed",
        "document_id": document_id,
        "source": str(path),
        "staging": str(staging_path),
        "quality": quality,
        "page_count": ocr.page_count,
        "avg_confidence": ocr.avg_confidence,
        "validations": validations_summary(validations),
        "chunks": len(chunks),
        "review_html": str(review_path),
        "plan_detection": detection.to_dict(),
    }


def _ocr_from_extracted(doc, *, file_hash: str) -> OcrResult:
    pages_json = doc.meta.get("pages") or []
    pages = []
    for row in pages_json:
        pages.append(
            OcrPage(
                page_number=int(row.get("page", 0)),
                text_raw=row.get("text_raw") or row.get("text") or "",
                text_normalized=row.get("text") or row.get("text_raw") or "",
                confidence=row.get("confidence"),
                status=row.get("status", "pass"),
                blocks=[OcrBlock.from_dict(b) for b in (row.get("blocks") or [])],
            )
        )
    return OcrResult(
        source_path=doc.source_path,
        file_hash=file_hash,
        engine=doc.meta.get("engine", "unknown"),
        engine_version=doc.meta.get("model_id", ""),
        model_id=doc.meta.get("model_id", ""),
        pages=pages,
        quality=doc.quality,
        notes=doc.notes,
        meta=doc.meta,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker OCR reanudable (C4)")
    parser.add_argument("--file", type=Path, help="PDF/imagen a procesar")
    parser.add_argument("--ifc", action="store_true", help="Piloto IFC-078 lote 1")
    parser.add_argument("--document-id", default="IFC-078", help="ID carpeta staging")
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--force", action="store_true", help="Reprocesar aunque exista staging")
    parser.add_argument(
        "--allow-non-plano",
        action="store_true",
        help="No bloquear OCR si el PDF no parece plano",
    )
    parser.add_argument(
        "--scan-plans",
        action="store_true",
        help="Listar planos detectados en corpus y salir",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    settings = get_ocr_settings()

    if args.scan_plans:
        from mmi.tools.plan_scan import scan_corpus

        payload = scan_corpus(DEFAULT_CORPUS)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"OCR provider: {settings.provider} · min_page={settings.min_page_confidence}")

    path = args.file
    document_key = args.document_id
    version_label = ""
    tipo = "plano"
    if args.ifc:
        corpus = DEFAULT_CORPUS
        files, _ = resolve_lote1(corpus)
        match = next((f for f in files if f.get("is_plano") is True), None)
        if not match:
            from mmi.ingest.plan_detect import detect_plan

            for pdf in sorted(DEFAULT_CORPUS.rglob("*.pdf")):
                det = detect_plan(pdf)
                if det.is_plano and det.confidence >= 0.55:
                    match = {
                        "absolute_path": str(pdf),
                        "document_key": pdf.stem[:40],
                        "revision": "",
                        "suggested_tipo": "plano",
                        "plan_detection": det.to_dict(),
                    }
                    break
        if not match:
            print("No hay plano OCR en lote 1. Ejecuta: python -m mmi.tools.plan_scan --plano-only")
            return 1
        path = Path(match["absolute_path"])
        document_key = match.get("document_key") or path.stem.replace(" ", "_")[:60]
        version_label = match.get("revision") or ""
        tipo = match.get("suggested_tipo") or "plano"
        det = match.get("plan_detection") or {}
        print(f"Piloto: {path.name} · plano={det.get('is_plano')} conf={det.get('confidence')}")

    if path is None:
        print("Usa --file o --ifc")
        return 1

    try:
        result = run_ocr_job(
            path,
            document_id=args.document_id,
            out_root=args.out,
            document_key=document_key,
            version_label=version_label,
            tipo=tipo,
            skip_existing=not args.force,
            require_plano=not args.allow_non_plano,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("quality") in {"pass", "review", None} else 1


if __name__ == "__main__":
    raise SystemExit(main())
