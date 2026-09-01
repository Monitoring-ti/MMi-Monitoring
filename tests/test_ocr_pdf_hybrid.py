"""Tests PDF híbrido C4.9 (sin Azure)."""

from unittest.mock import patch

from mmi.ingest.pdf import PageBlock, PdfAdapter


def test_extract_hybrid_uses_native_when_all_pages_have_text(tmp_path):
    adapter = PdfAdapter()
    pages = [
        PageBlock(page=1, text="nativo", needs_ocr=False, char_count=6),
        PageBlock(page=2, text="otra", needs_ocr=False, char_count=4),
    ]
    with patch.object(adapter, "_read_pages", return_value=pages):
        doc = adapter.extract_hybrid(tmp_path / "fake.pdf")
    assert doc.meta["format"] == "pdf"
    assert doc.quality == "pass"


def test_extract_hybrid_delegates_full_ocr_when_no_native_text(tmp_path):
    adapter = PdfAdapter()
    pages = [PageBlock(page=1, text="", needs_ocr=True, char_count=0)]
    fake_ocr = type(
        "Doc",
        (),
        {
            "quality": "review",
            "ocr_confidence": 0.8,
            "meta": {"engine": "azure"},
        },
    )()
    with patch.object(adapter, "_read_pages", return_value=pages):
        with patch("mmi.ingest.ocr.extract_with_ocr", return_value=fake_ocr):
            doc = adapter.extract_hybrid(tmp_path / "scan.pdf")
    assert doc is fake_ocr
