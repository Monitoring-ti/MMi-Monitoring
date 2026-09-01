"""Tests Motor MMI M2 (sin red)."""

import json
from unittest.mock import MagicMock, patch

from mmi.motor.analyze import (
    build_search_query,
    parse_motor_response,
    resolve_asset,
)
from mmi.motor.payloads import motor_analyze_payload, motor_details_payload
from mmi.motor.session import MotorSession, MotorSessionStore


def test_build_search_query():
    q = build_search_query("alta temperatura", {"id": "CTS-DCH-ENF", "name": "Sistema enfriamiento", "modulo": "ODS1"})
    assert "alta temperatura" in q
    assert "ODS1" in q


def test_parse_motor_response_strips_fences():
    raw = """```json
{"diagnosis": {"summary": "ok", "confidence_label": "alta", "confidence_pct": 90},
 "verified_facts": [], "hypotheses": [], "physical_checks": [], "discrepancies": []}
```"""
    data = parse_motor_response(raw)
    assert data["diagnosis"]["summary"] == "ok"


def test_resolve_asset_from_fixture():
    asset = resolve_asset("CTS-DCH-ENF")
    assert asset["id"] == "CTS-DCH-ENF"


def test_motor_analyze_payload_shape():
    from mmi.motor.analyze import MotorAnalysisResult

    result = MotorAnalysisResult(
        asset={"id": "X", "name": "X"},
        symptom="s",
        window="24h",
        diagnosis={"summary": "d", "confidence_label": "media", "confidence_pct": 70},
        verified_facts=[],
        hypotheses=[{"id": "H1", "title": "t", "confidence_pct": 60}],
        physical_checks=[],
        discrepancies=[],
        sources_preview=["doc.pdf"],
        references=[],
        hits=[],
        model="test-model",
    )
    payload = motor_analyze_payload(result, "mid123", 1200)
    assert payload["motor_id"] == "mid123"
    assert payload["elapsed_ms"] == 1200
    assert payload["hypotheses"][0]["id"] == "H1"


def test_motor_session_store_roundtrip():
    store = MotorSessionStore()
    session = MotorSession(
        asset_id="A",
        symptom="s",
        window="24h",
        hits=[],
        analysis={"hypotheses": []},
        references=[],
        model="m",
    )
    mid = store.put(session)
    assert store.get(mid) is not None


def test_analyze_motor_no_hits():
    from mmi.motor.analyze import analyze_motor

    engine = MagicMock()
    engine.search.return_value = []
    result = analyze_motor("UNKNOWN-ASSET", "falla bomba", engine)
    assert result.diagnosis["confidence_pct"] == 0
    assert result.physical_checks


def test_analyze_motor_no_hits_with_sensors():
    from mmi.motor.analyze import analyze_motor

    engine = MagicMock()
    engine.search.return_value = []
    result = analyze_motor("CTS-DCH-ENF", "falla bomba", engine)
    assert result.verified_facts
    assert any(f.get("sensor") for f in result.verified_facts)


def test_analyze_motor_with_mock_llm():
    from mmi.motor.analyze import analyze_motor
    from mmi.search.engine import SearchResult

    hit = SearchResult(
        point_id="p1",
        score=0.9,
        content="Temperatura límite 95 C en ATM",
        document_id="d1",
        tipo="guia",
        dominio="mantenibilidad",
        criticality_level="normal",
        section_path="s1",
        page_start=1,
        page_end=2,
        asset_codes=[],
        chunk_index=0,
        titulo="ATM enfriamiento",
        citation="ATM · p.1",
    )
    engine = MagicMock()
    engine.search.return_value = [hit]
    llm_json = json.dumps(
        {
            "diagnosis": {"summary": "Posible sobrecalentamiento", "confidence_label": "media", "confidence_pct": 75},
            "verified_facts": [
                {"text": "Límite 95 C documentado", "kind": "document", "citation_index": 1}
            ],
            "hypotheses": [
                {"id": "H1", "title": "Restricción flujo", "rationale": "r", "confidence_pct": 70, "supported_fact_indices": [1]}
            ],
            "physical_checks": [{"text": "Medir T salida", "priority": "urgent"}],
            "discrepancies": [],
        }
    )
    with patch("mmi.motor.analyze.chat_completion", return_value=llm_json):
        result = analyze_motor("CTS-DCH-ENF", "alta temperatura", engine)
    assert result.verified_facts[0]["source"]["citation"]
    assert len(result.hypotheses) >= 2
    assert all(h.get("kind") == "inference" for h in result.hypotheses)
