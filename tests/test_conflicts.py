"""Tests detección de contradicciones C2 (sin red)."""

from mmi.search.conflicts import (
    conflict_banner,
    detect_conflicts,
    detect_numeric_conflicts,
    detect_pptx_rpn_conflicts,
    detect_superseded_leak,
    detect_version_conflicts,
    infer_document_key,
)
from mmi.search.engine import SearchResult


def _hit(
    *,
    titulo: str = "doc",
    content: str = "",
    version_label: str | None = None,
    tipo: str = "guia",
    document_key: str | None = None,
    version_status: str | None = None,
    is_current: bool = True,
    section_path: str | None = None,
) -> SearchResult:
    return SearchResult(
        point_id="p1",
        score=0.5,
        content=content,
        document_id="d1",
        tipo=tipo,
        dominio=None,
        criticality_level="normal",
        section_path=section_path,
        page_start=1,
        page_end=1,
        asset_codes=[],
        chunk_index=0,
        version_label=version_label,
        titulo=titulo,
        citation=titulo,
        document_key=document_key,
        version_status=version_status,
        is_current=is_current,
    )


def test_infer_document_key_strips_revision():
    hit = _hit(titulo="SGP-07MYC-GUIGS-00001 Rev 6 alcance")
    key = infer_document_key(hit)
    assert "REV" not in key
    assert "GUIGS" in key


def test_detect_version_conflicts_same_document_key():
    hits = [
        _hit(titulo="GUIGS alcance", version_label="Rev 5", document_key="SGP-GUIGS"),
        _hit(titulo="GUIGS alcance", version_label="Rev 6", document_key="SGP-GUIGS"),
    ]
    rows = detect_version_conflicts(hits)
    assert len(rows) == 1
    assert rows[0]["kind"] == "version"
    assert "Rev 5" in rows[0]["versions"]
    assert "Rev 6" in rows[0]["versions"]


def test_detect_numeric_conflicts_temperature():
    hits = [
        _hit(titulo="GUIGS límites", content="alarma 85 °C en sensor", document_key="GUIGS"),
        _hit(titulo="GUIGS límites", content="límite máximo 92 °C", document_key="GUIGS"),
    ]
    rows = detect_numeric_conflicts(hits)
    assert any(r["kind"] == "numeric" and r["metric"] in {"temp_c", "limit_c"} for r in rows)


def test_detect_pptx_rpn_conflicts():
    hits = [
        _hit(tipo="presentacion", section_path="slide 3", content="RPN 120 criticidad alta"),
        _hit(tipo="presentacion", section_path="slide 7", content="RPN 240 acción inmediata"),
    ]
    rows = detect_pptx_rpn_conflicts(hits)
    assert len(rows) == 1
    assert rows[0]["kind"] == "pptx_rpn"
    assert rows[0]["values"] == [120, 240]


def test_detect_superseded_leak():
    hits = [
        _hit(titulo="GUIGS Rev 5", version_status="superseded", is_current=False),
        _hit(titulo="GUIGS Rev 6", version_status="active", is_current=True),
    ]
    rows = detect_superseded_leak(hits)
    assert len(rows) == 1
    assert rows[0]["kind"] == "superseded"


def test_detect_conflicts_pipeline_dedupes():
    hits = [
        _hit(titulo="GUIGS Rev 5", version_label="Rev 5", version_status="superseded", is_current=False),
        _hit(titulo="GUIGS Rev 6", version_label="Rev 6", version_status="active", is_current=True),
    ]
    rows = detect_conflicts(hits)
    kinds = {r["kind"] for r in rows}
    assert "superseded" in kinds
    assert "version" in kinds


def test_conflict_banner_empty():
    banner = conflict_banner([])
    assert banner["visible"] is False
    assert banner["count"] == 0


def test_conflict_banner_warn():
    banner = conflict_banner([{"severity": "warn", "text": "x"}])
    assert banner["visible"] is True
    assert banner["severity"] == "warn"
    assert "conflicto" in banner["message"].lower()
