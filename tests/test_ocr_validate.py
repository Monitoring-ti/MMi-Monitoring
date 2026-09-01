"""Tests validación OCR C4 (sin red)."""

from mmi.catalog.assets import CatalogAsset
from mmi.config import OcrSettings
from mmi.ingest.ocr_models import OcrBlock, OcrPage, OcrResult
from mmi.ingest.ocr_validate import (
    validate_ocr_result,
    validate_page_confidence,
    validate_technical_tags,
    validations_summary,
)


def _settings() -> OcrSettings:
    return OcrSettings(
        provider="azure",
        azure_endpoint="",
        azure_key="",
        azure_model="prebuilt-layout",
        min_page_confidence=0.75,
        min_block_confidence=0.60,
        critical_field_confidence=0.90,
        dpi=300,
    )


def test_validate_page_confidence_flags_low_score():
    page = OcrPage(page_number=1, text_raw="texto", confidence=0.5)
    rows = validate_page_confidence(page, _settings())
    assert len(rows) == 1
    assert rows[0].rule == "page_confidence"
    assert rows[0].status == "review"


def test_validate_technical_tag_in_catalog():
    catalog = {"IFC-078": CatalogAsset(id="1", asset_tag="IFC-078")}
    rows = validate_technical_tags(
        "Plano IFC-078 torre enfriamiento",
        catalog=catalog,
        settings=_settings(),
        page_number=1,
        confidence=0.95,
    )
    assert any(r.status == "pass" for r in rows)


def test_validate_technical_tag_unknown_is_review():
    rows = validate_technical_tags(
        "Equipo XYZ-9999",
        catalog={},
        settings=_settings(),
        page_number=1,
    )
    assert rows
    assert rows[0].status == "review"


def test_validate_ocr_result_raw_normalized_diff():
    ocr = OcrResult(
        source_path="/tmp/test.pdf",
        file_hash="abc",
        engine="test",
        engine_version="1",
        model_id="test",
        pages=[
            OcrPage(
                page_number=1,
                text_raw="IFC-0 78",
                text_normalized="IFC-078",
                confidence=0.9,
                blocks=[
                    OcrBlock(
                        block_index=0,
                        block_type="line",
                        text_raw="IFC-0 78",
                        text_normalized="IFC-078",
                        confidence=0.9,
                    )
                ],
            )
        ],
    )
    validations, quality = validate_ocr_result(ocr, catalog={}, settings=_settings())
    assert any(v.rule == "raw_normalized_diff" for v in validations)
    assert quality in {"pass", "review"}


def test_validations_summary_counts():
    from mmi.ingest.ocr_validate import OcrValidation

    rows = [
        OcrValidation(rule="a", status="pass"),
        OcrValidation(rule="b", status="review"),
    ]
    summary = validations_summary(rows)
    assert summary["pass"] == 1
    assert summary["review"] == 1
