"""Fase 0: manifest lote 1 + extracción Excel/PDF."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from mmi.corpus.lote1 import resolve_lote1
from mmi.index.chunking import file_sha256
from mmi.ingest.docx import DocxAdapter, save_blocks_json
from mmi.ingest.excel import ExcelAdapter
from mmi.ingest.ocr import extract_with_ocr
from mmi.ingest.pdf import PdfAdapter, pages_to_json
from mmi.ingest.pptx import PptxAdapter, save_slides_json


def build_lote1_manifest(corpus_root: Path) -> dict:
    files, missing = resolve_lote1(corpus_root)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lote": "lote1-rev6-vigente",
        "policy": "Guía Rev 6 como is_current; excluye Rev 4/5 y SOP BCK",
        "count": len(files),
        "local_ready": len(files),
        "online_only": 0,
        "missing": missing,
        "files": files,
    }


def _slug(path: Path) -> str:
    return path.stem.replace(" ", "_")[:60]


def _write_extract(target: Path, payload: dict, markdown: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    target.joinpath("extracted.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    target.joinpath("extracted.md").write_text(markdown, encoding="utf-8")


def _should_skip_extraction(path: Path, target: Path) -> tuple[bool, str | None]:
    """Omite extracción si extracted.json existe y el SHA-256 del archivo coincide."""
    meta_path = target / "extracted.json"
    if not meta_path.exists():
        return False, None
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, None
    stored_hash = payload.get("file_hash")
    if not stored_hash:
        return False, None
    current_hash = file_sha256(path)
    if stored_hash == current_hash:
        return True, current_hash
    return False, current_hash


def process_phase0_files(manifest: dict, out_dir: Path) -> list[dict]:
    excel = ExcelAdapter()
    pdf = PdfAdapter()
    results: list[dict] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for entry in manifest.get("files") or []:
        phase0 = entry.get("phase0", "")
        if phase0 not in {"excel", "pdf", "ocr", "pptx", "docx"}:
            continue

        path = Path(entry["absolute_path"])
        target = out_dir / _slug(path)
        skip, file_hash = _should_skip_extraction(path, target)
        if skip:
            try:
                prev = json.loads((target / "extracted.json").read_text(encoding="utf-8"))
                quality = prev.get("quality", "unknown")
            except (OSError, json.JSONDecodeError):
                quality = "unknown"
            row = {
                "name": entry["name"],
                "phase0": phase0,
                "quality": quality,
                "out": str(target),
                "indexable": quality == "pass",
                "skipped": True,
                "file_hash": file_hash[:12] if file_hash else None,
            }
            results.append(row)
            print(f"  [SKIP] {entry['name']} — sin cambios (sha256 {file_hash[:12] if file_hash else '?'})")
            continue

        file_hash = file_hash or file_sha256(path)

        if phase0 == "excel":
            doc = excel.extract(path)
            payload = {
                "format": "excel",
                "source_path": doc.source_path,
                "file_hash": file_hash,
                "quality": doc.quality,
                "notes": doc.notes,
                "meta": doc.meta,
                "sheets": [asdict(s) for s in doc.sheets],
                "records": [
                    {"sheet": r.sheet, "row": r.row, "values": r.values, "text_line": r.text_line}
                    for r in doc.records
                ],
            }
            detail = f"{len(doc.records)} filas"
        elif phase0 == "pptx":
            pptx = PptxAdapter()
            presentation = pptx.extract(
                path,
                file_hash=file_hash,
                document_key=entry.get("document_key"),
            )
            doc = pptx.to_extracted_document(presentation)
            save_slides_json(presentation, target)
            payload = {
                "format": "pptx",
                "source_path": presentation.source_path,
                "file_hash": file_hash,
                "quality": presentation.quality,
                "notes": presentation.notes,
                "meta": presentation.meta,
                "slides_file": "slides.json",
                "slide_count": presentation.slide_count,
                "slides_pass": presentation.slides_pass,
            }
            detail = (
                f"{presentation.slides_pass}/{presentation.slide_count} diapositivas indexables"
            )
        elif phase0 == "docx":
            docx = DocxAdapter()
            document = docx.extract(
                path,
                file_hash=file_hash,
                document_key=entry.get("document_key"),
            )
            doc = docx.to_extracted_document(document)
            save_blocks_json(document, target)
            payload = {
                "format": "docx",
                "source_path": document.source_path,
                "file_hash": file_hash,
                "quality": document.quality,
                "notes": document.notes,
                "meta": document.meta,
                "blocks_file": "blocks.json",
                "block_count": document.block_count,
                "blocks_pass": document.blocks_pass,
            }
            detail = f"{document.blocks_pass}/{document.block_count} bloques indexables"
        elif phase0 == "ocr":
            doc = extract_with_ocr(path, file_hash=file_hash)
            pages_data = doc.meta.get("pages") or []
            payload = {
                "format": "ocr",
                "source_path": doc.source_path,
                "file_hash": file_hash,
                "quality": doc.quality,
                "notes": doc.notes,
                "ocr_confidence": doc.ocr_confidence,
                "meta": {k: v for k, v in doc.meta.items() if k != "pages"},
                "pages": pages_data,
            }
            ocr_path = target / "ocr_result.json"
            ocr_path.write_text(
                json.dumps(pages_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            payload["ocr_result_file"] = "ocr_result.json"
            detail = (
                f"{doc.meta.get('pages_with_text', 0)}/{doc.meta.get('page_count', 0)} págs OCR "
                f"(conf. {doc.ocr_confidence:.0%})" if doc.ocr_confidence else
                f"{doc.meta.get('pages_with_text', 0)}/{doc.meta.get('page_count', 0)} págs OCR"
            )
        else:
            pages = pdf._read_pages(path)
            doc = pdf._build_document(path, pages)
            payload = {
                "format": "pdf",
                "source_path": doc.source_path,
                "file_hash": file_hash,
                "quality": doc.quality,
                "notes": doc.notes,
                "meta": {k: v for k, v in doc.meta.items() if k != "pages"},
                "pages": pages_to_json(pages),
            }
            detail = f"{doc.meta.get('pages_with_text', 0)}/{doc.meta.get('page_count', 0)} págs con texto"

        _write_extract(target, payload, doc.markdown)
        row = {
            "name": entry["name"],
            "phase0": phase0,
            "quality": doc.quality,
            "out": str(target),
            "indexable": doc.quality == "pass",
            "skipped": False,
            "file_hash": file_hash[:12],
        }
        if phase0 == "excel":
            row["sheets"] = len(doc.sheets)
            row["records"] = len(doc.records)
        elif phase0 == "pptx":
            row["slides"] = presentation.slide_count
            row["slides_pass"] = presentation.slides_pass
        elif phase0 == "docx":
            row["blocks"] = document.block_count
            row["blocks_pass"] = document.blocks_pass
        elif phase0 == "ocr":
            row["pages"] = doc.meta.get("page_count", 0)
            row["pages_with_text"] = doc.meta.get("pages_with_text", 0)
            row["ocr_confidence"] = doc.ocr_confidence
        else:
            row["pages"] = doc.meta.get("page_count", 0)
            row["pages_with_text"] = doc.meta.get("pages_with_text", 0)

        results.append(row)
        mark = "OK" if doc.quality == "pass" else doc.quality.upper()
        print(f"  [{mark}] {entry['name']} — {detail} → {target}")

    return results


def _docx_entries_from_corpus(corpus: Path, *, only: Path | None = None) -> list[dict]:
    entries: list[dict] = []
    paths: list[Path]
    if only:
        paths = [only.resolve()]
    else:
        paths = sorted(corpus.rglob("*.docx"))
    for path in paths:
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(corpus)
        except ValueError:
            rel = path.name
        rev = ""
        name_lower = path.name.lower()
        for token in ("rev ", "rev.", " rev"):
            if token in name_lower:
                rev = path.stem[name_lower.index(token.strip()) :][:20]
                break
        entries.append(
            {
                "id": f"docx-{path.stem[:40]}",
                "name": path.name,
                "absolute_path": str(path.resolve()),
                "relative_path": str(rel),
                "extension": path.suffix.lower(),
                "phase0": "docx",
                "document_key": "",
                "revision": rev,
                "suggested_tipo": "guia",
                "ready": True,
            }
        )
    return entries


def process_docx_corpus(
    corpus: Path,
    out_dir: Path,
    *,
    only: Path | None = None,
) -> list[dict]:
    """Fase 0 DOCX para archivos del corpus (fuera del lote 1)."""
    manifest = {"files": _docx_entries_from_corpus(corpus, only=only)}
    return process_phase0_files(manifest, out_dir)


def _refresh_dashboard(manifest_path: Path, extract_dir: Path, out_dir: Path) -> None:
    from mmi.analysis.status import collect_analysis_status, render_dashboard, write_review_pages
    from mmi.tools.source_review import render_source_review_page
    from mmi.corpus.remote_source import load_remote_source

    write_review_pages(extract_dir)
    status_payload = collect_analysis_status(manifest_path, extract_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "analysis-status.json").write_text(
        json.dumps(status_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "analysis-status.html").write_text(
        render_dashboard(status_payload), encoding="utf-8"
    )
    remote = load_remote_source(out_dir / "remote-source.json")
    (out_dir / "source-review.html").write_text(
        render_source_review_page(remote), encoding="utf-8"
    )
    print(f"Dashboard → {(out_dir / 'analysis-status.html').resolve()}")
    print(f"Enlace nube → {(out_dir / 'source-review.html').resolve()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manifest + Fase 0 del lote 1 (Rev 6)")
    parser.add_argument("--corpus", type=Path, default=Path("00 DOCUMENTOS NCC30"))
    parser.add_argument("--manifest", type=Path, default=Path("out/process-manifest.json"))
    parser.add_argument("--extract-dir", type=Path, default=Path("out/lote1-extract"))
    parser.add_argument("--write-only", action="store_true")
    parser.add_argument("--pdf-only", action="store_true", help="Solo procesar PDF/OCR")
    parser.add_argument("--excel-only", action="store_true", help="Solo procesar Excel")
    parser.add_argument("--pptx-only", action="store_true", help="Solo procesar PPTX")
    parser.add_argument("--ocr-only", action="store_true", help="Solo procesar OCR (IFC-078)")
    parser.add_argument("--docx-only", action="store_true", help="Solo procesar DOCX (corpus o --docx-path)")
    parser.add_argument("--docx-path", type=Path, help="Un solo .docx para extracción piloto")
    parser.add_argument(
        "--docx-extract-dir",
        type=Path,
        default=Path("out/docx-extract"),
        help="Directorio de salida para --docx-only",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    repo = Path.cwd()
    corpus = args.corpus if args.corpus.is_absolute() else repo / args.corpus

    if args.docx_only:
        docx_path = args.docx_path
        if docx_path and not docx_path.is_absolute():
            docx_path = repo / docx_path
        extract_dir = args.docx_extract_dir if args.docx_extract_dir.is_absolute() else repo / args.docx_extract_dir
        extract_dir.mkdir(parents=True, exist_ok=True)
        print("\nExtracción Fase 0 DOCX:")
        results = process_docx_corpus(corpus, extract_dir, only=docx_path)
        summary_path = extract_dir / "phase0-summary.json"
        summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nResumen → {summary_path}")
        write_review = __import__("mmi.analysis.status", fromlist=["write_review_pages"]).write_review_pages
        write_review(extract_dir)
        failed = [r for r in results if not r["indexable"]]
        return 0 if not failed else 1

    manifest = build_lote1_manifest(corpus)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest.resolve()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifest: {manifest_path} ({manifest['count']} archivos)")

    if manifest["missing"]:
        print("Faltan en disco:")
        for name in manifest["missing"]:
            print(f"  - {name}")

    pending_pptx = [f["name"] for f in manifest["files"] if f.get("phase0") == "pptx"]
    pending_docx = [
        f["name"]
        for f in (manifest.get("files") or [])
        if Path(f.get("name", "")).suffix.lower() == ".docx"
    ]
    if pending_pptx and args.write_only:
        print("PPTX en manifest (ejecutar sin --write-only para extraer):")
        for name in pending_pptx:
            print(f"  - {name}")
    if pending_docx and args.write_only:
        docx_count = len(list(corpus.rglob("*.docx")))
        print(f"DOCX en corpus: {docx_count} archivos — ejecutar --docx-only para extraer (B7)")

    if args.write_only:
        return 0 if not manifest["missing"] else 1

    files = manifest["files"]
    if args.pdf_only:
        files = [f for f in files if f.get("phase0") in {"pdf", "ocr"}]
    elif args.excel_only:
        files = [f for f in files if f.get("phase0") == "excel"]
    elif args.pptx_only:
        files = [f for f in files if f.get("phase0") == "pptx"]
    elif args.ocr_only:
        files = [f for f in files if f.get("phase0") == "ocr"]
    elif args.docx_only:
        files = [f for f in files if f.get("phase0") == "docx"]
    manifest = {**manifest, "files": files}

    print("\nExtracción Fase 0:")
    results = process_phase0_files(manifest, args.extract_dir)
    summary_path = args.extract_dir / "phase0-summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResumen → {summary_path}")

    _refresh_dashboard(manifest_path, args.extract_dir.resolve(), args.manifest.parent)

    failed = [r for r in results if not r["indexable"]]
    return 0 if not manifest["missing"] and not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
