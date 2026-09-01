"""Tests detección de planos (sin red)."""

from pathlib import Path

from mmi.ingest.pdf import PageBlock
from mmi.ingest.plan_detect import detect_plan

CORPUS = Path("ODS1 TORR ENF DCH")


def test_ifc_078_detected_as_document_not_plano():
    path = CORPUS / "00 DOCUMENTOS NCC30" / "IFC 078_REV15 28122020 (1).pdf"
    if not path.exists():
        return
    det = detect_plan(path)
    assert det.is_plano is False
    assert det.block_ocr is True
    assert det.suggested_phase0 == "pdf"
    assert det.avg_chars_per_page > 500


def test_engineering_pdf_detected_as_plano():
    path = (
        CORPUS
        / "02 INF TEC"
        / "08-01-2025 FT"
        / "4600027995-06950-201ME-00001 Diagrama Instrumentación.pdf"
    )
    if not path.exists():
        return
    det = detect_plan(path)
    assert det.is_plano is True
    assert det.block_ocr is False


def test_detect_from_page_blocks_without_file():
    pages = [
        PageBlock(page=1, text="Instructivo financiero contable gerencia", needs_ocr=False, char_count=1200),
        PageBlock(page=2, text="Activo fijo propiedad planta y equipo", needs_ocr=False, char_count=1100),
    ]
    det = detect_plan(Path("fake-instructivo.pdf"), pages=pages)
    assert det.is_plano is False
    assert det.kind == "documento"


def test_scanned_pages_detected_as_plano():
    pages = [
        PageBlock(page=1, text="", needs_ocr=True, char_count=0),
        PageBlock(page=2, text="escala 1:100", needs_ocr=True, char_count=12),
    ]
    det = detect_plan(Path("4400285992-06500-100EL-00001.pdf"), pages=pages)
    assert det.is_plano is True
    assert det.suggested_phase0 == "ocr"


def test_lote1_ifc_switches_phase0():
    from mmi.corpus.lote1 import resolve_lote1
    from mmi.corpus.paths import DEFAULT_CORPUS

    if not DEFAULT_CORPUS.exists():
        return
    files, missing = resolve_lote1(DEFAULT_CORPUS)
    ifc = next((f for f in files if f.get("document_key") == "IFC-078"), None)
    assert ifc is not None
    assert ifc["phase0"] == "pdf"
    assert ifc["plan_detection"]["is_plano"] is False
