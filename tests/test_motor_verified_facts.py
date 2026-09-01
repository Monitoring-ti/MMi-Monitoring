"""Tests Motor MMI M3 — hechos verificados (sin red)."""

from datetime import datetime, timezone

from mmi.motor.oem_limits import extract_limits_from_text
from mmi.motor.sensors import SensorReading, get_sensor_readings
from mmi.motor.verified_facts import (
    build_measurement_facts,
    compute_aggregate_confidence,
    merge_verified_facts,
)
from mmi.search.engine import SearchResult


def _hit(content: str, *, titulo: str = "ATM enfriamiento", citation: str = "ATM · p.1") -> SearchResult:
    return SearchResult(
        point_id="p1",
        score=0.9,
        content=content,
        document_id="d1",
        tipo="guia",
        dominio="mantenibilidad",
        criticality_level="normal",
        section_path="s1",
        page_start=1,
        page_end=2,
        asset_codes=[],
        chunk_index=0,
        titulo=titulo,
        citation=citation,
    )


def test_extract_limits_max_temp():
    text = "TE-401A temperatura máxima de alarma 95 °C en salida intercambiador."
    limits = extract_limits_from_text(text, tag="TE-401A")
    assert limits
    assert limits[0].value == 95.0
    assert limits[0].unit == "°C"


def test_extract_limits_nominal_flow():
    text = "FT-405 caudal nominal de diseño 150 L/min en circuito principal."
    limits = extract_limits_from_text(text, tag="FT-405")
    assert limits
    assert any(l.value == 150.0 for l in limits)


def test_get_sensor_readings_fixture():
    readings = get_sensor_readings("CTS-DCH-ENF", window="24h")
    tags = {r.tag for r in readings}
    assert "TE-401A" in tags
    assert "FT-405" in tags
    assert "VE-402X" in tags


def test_build_measurement_facts_cts_demo():
    readings = get_sensor_readings("CTS-DCH-ENF", window="24h")
    hits = [
        _hit("TE-401A límite máximo temperatura 95 °C según ATM sistema enfriamiento."),
        _hit("FT-405 caudal nominal 150 L/min en FMECA enfriamiento CTS DCH."),
        _hit("VE-402X vibración máxima 4.5 mm/s en manual OEM bomba."),
    ]
    facts = build_measurement_facts(readings, hits)
    assert len(facts) == 3
    te = next(f for f in facts if f["sensor"]["tag"] == "TE-401A")
    assert te["limit"]["exceeded"] is True
    assert te["limit"]["value"] == 95.0
    assert te["source"]["type"] == "document"


def test_merge_verified_facts_dedupes_by_tag():
    structured = [{"text": "TE-401A", "sensor": {"tag": "TE-401A"}}]
    llm = [{"text": "TE-401A temperatura alta", "kind": "measurement"}]
    merged = merge_verified_facts(structured, llm)
    assert len(merged) == 1


def test_compute_aggregate_confidence():
    facts = [
        {
            "confidence": {"pct": 90},
            "source": {"type": "document"},
            "limit": {"exceeded": True},
        },
        {
            "confidence": {"pct": 85},
            "source": {"type": "document"},
            "limit": {"exceeded": False},
        },
    ]
    diag = compute_aggregate_confidence(facts, {"summary": "x", "confidence_pct": 50})
    assert diag["confidence_pct"] >= 85
    assert diag["confidence_label"] == "alta"
    assert diag["verified_fact_count"] == 2


def test_analyze_motor_includes_structured_facts():
    from unittest.mock import MagicMock, patch

    from mmi.motor.analyze import analyze_motor

    hit = _hit("TE-401A límite máximo 95 °C")
    engine = MagicMock()
    engine.search.return_value = [hit]
    llm_json = (
        '{"diagnosis":{"summary":"Sobrecalentamiento","confidence_label":"media","confidence_pct":70},'
        '"verified_facts":[],"hypotheses":[{"id":"H1","title":"Restricción","rationale":"r",'
        '"confidence_pct":70,"supported_fact_indices":[1]}],'
        '"physical_checks":[{"text":"Medir T","priority":"urgent"}],"discrepancies":[]}'
    )
    with patch("mmi.motor.analyze.chat_completion", return_value=llm_json):
        result = analyze_motor("CTS-DCH-ENF", "alta temperatura", engine)
    assert any(f.get("sensor", {}).get("tag") == "TE-401A" for f in result.verified_facts)
    assert result.diagnosis.get("verified_fact_count", 0) >= 1
