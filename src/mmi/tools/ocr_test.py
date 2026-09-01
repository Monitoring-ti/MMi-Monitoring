"""CLI para verificar y probar Azure Document Intelligence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from mmi.config import get_ocr_settings
from mmi.corpus.lote1 import resolve_lote1
from mmi.corpus.paths import DEFAULT_CORPUS
from mmi.ingest.ocr import extract_with_ocr
from mmi.ingest.ocr_azure import AzureDocumentIntelligenceAdapter


def _mask(s: str) -> str:
    if len(s) <= 8:
        return "(vacío)" if not s else "****"
    return s[:8] + "…" + s[-4:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probar conexión Azure Document Intelligence")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Solo verificar variables de entorno y cliente Azure",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Analizar un PDF/imagen con OCR (ruta absoluta o relativa)",
    )
    parser.add_argument(
        "--ifc",
        action="store_true",
        help="Analizar IFC-078 del lote 1 (piloto OCR)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("out/ocr-test.json"),
        help="Guardar resultado JSON del análisis",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    settings = get_ocr_settings()

    print("=== Configuración OCR ===")
    print(f"  MMI_OCR_PROVIDER     = {settings.provider}")
    print(f"  AZURE_ENDPOINT       = {settings.azure_endpoint or '(vacío)'}")
    print(f"  AZURE_KEY            = {_mask(settings.azure_key)}")
    print(f"  AZURE_MODEL          = {settings.azure_model}")
    print(f"  MIN_PAGE_CONFIDENCE  = {settings.min_page_confidence}")

    if not settings.azure_configured:
        print("\n❌ Faltan credenciales Azure en .env")
        print("\nPasos:")
        print("  1. Portal Azure → Document Intelligence / AI Services")
        print("  2. Crear recurso (o usar existente)")
        print("  3. Keys and Endpoint → copiar Endpoint y Key 1")
        print("  4. Pegar en .env:")
        print("     AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://....cognitiveservices.azure.com/")
        print("     AZURE_DOCUMENT_INTELLIGENCE_KEY=...")
        return 1

    try:
        adapter = AzureDocumentIntelligenceAdapter(settings)
        info = adapter.test_connection()
        print(f"\n✓ Cliente Azure: {info.get('message', info.get('status'))}")
    except Exception as exc:  # noqa: BLE001
        print(f"\n❌ Error al crear cliente Azure: {exc}")
        return 1

    if args.check:
        return 0

    path: Path | None = args.file
    if args.ifc:
        corpus = DEFAULT_CORPUS
        files, missing = resolve_lote1(corpus)
        match = next((f for f in files if f.get("phase0") == "ocr"), None)
        if not match:
            print(f"No se encontró IFC-078 en lote 1 bajo {corpus}")
            if missing:
                print("Archivos faltantes:", ", ".join(missing))
            return 1
        path = Path(match["absolute_path"])
        print(f"\nPiloto OCR: {path.name}")

    if path is None:
        print("\nUsa --file <ruta> o --ifc para analizar un documento.")
        return 0

    if not path.exists():
        print(f"❌ No existe: {path}")
        return 1

    print(f"\nAnalizando con Azure ({settings.azure_model})…")
    try:
        doc = extract_with_ocr(path)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Error OCR: {exc}")
        return 1

    summary = {
        "source": doc.source_path,
        "quality": doc.quality,
        "ocr_confidence": doc.ocr_confidence,
        "page_count": doc.meta.get("page_count"),
        "pages_with_text": doc.meta.get("pages_with_text"),
        "engine": doc.meta.get("engine"),
        "model_id": doc.meta.get("model_id"),
        "notes": doc.notes,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✓ Calidad: {doc.quality}")
    print(f"  Páginas: {doc.meta.get('page_count')} · con texto: {doc.meta.get('pages_with_text')}")
    if doc.ocr_confidence is not None:
        print(f"  Confianza media: {doc.ocr_confidence:.2%}")
    if doc.notes:
        for n in doc.notes:
            print(f"  · {n}")
    print(f"\nResumen → {args.out.resolve()}")
    return 0 if doc.quality in {"pass", "review"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
