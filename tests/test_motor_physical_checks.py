"""Tests Motor MMI M5 — verificación física y export (sin red)."""

from mmi.motor.export_meta import build_export_meta
from mmi.motor.physical_checks import (
    generate_fallback_checks,
    prioritize_checks,
    process_physical_checks,
    validate_physical_check,
)


def _asset():
    return {"id": "CTS-DCH-ENF", "name": "Sistema enfriamiento", "criticality": "A"}


def _facts_exceeded():
    return [
        {"sensor": {"tag": "TE-401A"}, "limit": {"exceeded": True}},
        {"sensor": {"tag": "FT-405"}, "limit": {"exceeded": True}},
    ]


def test_validate_physical_check():
    row = validate_physical_check({"text": "  Medir T  ", "priority": "urgent"})
    assert row["text"] == "Medir T"
    assert row["priority"] == "urgent"
    assert row["checked"] is False


def test_prioritize_upgrades_on_critical_asset_with_alarms():
    checks = [{"text": "Rutina", "priority": "normal", "checked": False}]
    out = prioritize_checks(checks, asset=_asset(), facts=_facts_exceeded())
    assert out[0]["priority"] == "urgent"


def test_process_physical_checks_minimum_three():
    out = process_physical_checks([], asset=_asset(), facts=_facts_exceeded(), min_count=3)
    assert len(out) >= 3
    assert out[0]["priority"] == "urgent"


def test_generate_fallback_checks_from_sensors():
    out = generate_fallback_checks(_facts_exceeded(), asset=_asset())
    assert len(out) >= 2


def test_build_export_meta():
    from mmi.motor.analyze import MotorAnalysisResult

    result = MotorAnalysisResult(
        asset=_asset(),
        symptom="alta temperatura",
        window="24h",
        diagnosis={},
        verified_facts=[],
        hypotheses=[],
        physical_checks=[],
        discrepancies=[],
        sources_preview=[],
        references=[{"document_id": "doc-1", "citation": "ATM"}],
        hits=[],
        model="test-model",
    )
    meta = build_export_meta(result, "mid-abc")
    assert meta["motor_id"] == "mid-abc"
    assert meta["asset_id"] == "CTS-DCH-ENF"
    assert meta["model"] == "test-model"
    assert "doc-1" in meta["source_ids"]


def test_motor_payload_includes_export_meta():
    from mmi.motor.analyze import MotorAnalysisResult
    from mmi.motor.payloads import motor_analyze_payload

    result = MotorAnalysisResult(
        asset=_asset(),
        symptom="s",
        window="24h",
        diagnosis={},
        verified_facts=[],
        hypotheses=[],
        physical_checks=[{"text": "x", "priority": "urgent", "checked": False}],
        discrepancies=[],
        sources_preview=[],
        references=[],
        hits=[],
        model="m",
    )
    payload = motor_analyze_payload(result, "id1", 50)
    assert payload["export_meta"]["motor_id"] == "id1"
    assert len(payload["physical_checks"]) == 1
