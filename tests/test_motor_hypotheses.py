"""Tests Motor MMI M4 — hipótesis del sistema (sin red)."""

from mmi.motor.hypotheses import (
    INFERENCE_DISCLAIMER,
    generate_fallback_hypotheses,
    normalize_hypotheses,
    process_hypotheses,
    validate_hypothesis,
)


def _facts():
    return [
        {
            "text": "TE-401A 98 °C",
            "kind": "measurement",
            "sensor": {"tag": "TE-401A"},
            "limit": {"exceeded": True},
        },
        {
            "text": "FT-405 120 L/min",
            "kind": "measurement",
            "sensor": {"tag": "FT-405"},
            "limit": {"exceeded": True},
        },
        {
            "text": "VE-402X 5.2 mm/s",
            "kind": "measurement",
            "sensor": {"tag": "VE-402X"},
            "limit": {"exceeded": True},
        },
    ]


def test_validate_hypothesis_rejects_fact_kind():
    assert validate_hypothesis(
        {"title": "T", "rationale": "R", "kind": "measurement", "confidence_pct": 80, "supported_fact_indices": [1]},
        fact_count=1,
    ) is None


def test_validate_hypothesis_requires_supported_facts():
    assert validate_hypothesis(
        {"title": "T", "rationale": "R", "confidence_pct": 80, "supported_fact_indices": []},
        fact_count=2,
    ) is None


def test_normalize_hypotheses_ranks_and_links():
    facts = _facts()
    raw = [
        {"id": "X", "title": "Baja prioridad", "rationale": "r2", "confidence_pct": 40, "supported_fact_indices": [2]},
        {"id": "Y", "title": "Alta prioridad", "rationale": "r1", "confidence_pct": 90, "supported_fact_indices": [1, 2]},
    ]
    out = normalize_hypotheses(raw, facts)
    assert out[0]["id"] == "H1"
    assert out[0]["title"] == "Alta prioridad"
    assert out[0]["kind"] == "inference"
    assert out[0]["inference_disclaimer"] == INFERENCE_DISCLAIMER
    assert out[0]["supported_facts"][0]["index"] == 1


def test_generate_fallback_hypotheses_cts():
    out = generate_fallback_hypotheses(_facts())
    assert len(out) >= 2
    assert all(h["kind"] == "inference" for h in out)


def test_process_hypotheses_completes_minimum():
    facts = _facts()
    out = process_hypotheses(
        [{"title": "Solo una", "rationale": "r", "confidence_pct": 70, "supported_fact_indices": [1]}],
        facts,
        asset_id="CTS-DCH-ENF",
        min_count=2,
    )
    assert len(out) >= 2
    assert out[0]["confidence_pct"] >= out[1]["confidence_pct"]


def test_analyze_motor_no_hits_includes_hypotheses():
    from unittest.mock import MagicMock

    from mmi.motor.analyze import analyze_motor

    engine = MagicMock()
    engine.search.return_value = []
    result = analyze_motor("CTS-DCH-ENF", "falla bomba", engine)
    assert len(result.hypotheses) >= 2
    assert all(h.get("kind") == "inference" for h in result.hypotheses)


def test_motor_payload_includes_inference_disclaimer():
    from mmi.motor.analyze import MotorAnalysisResult
    from mmi.motor.payloads import motor_analyze_payload

    result = MotorAnalysisResult(
        asset={"id": "X"},
        symptom="s",
        window="24h",
        diagnosis={},
        verified_facts=[],
        hypotheses=[{"id": "H1", "title": "t", "kind": "inference"}],
        physical_checks=[],
        discrepancies=[],
        sources_preview=[],
        references=[],
        hits=[],
        model="m",
    )
    payload = motor_analyze_payload(result, "id1", 100)
    assert payload["inference_disclaimer"] == INFERENCE_DISCLAIMER
