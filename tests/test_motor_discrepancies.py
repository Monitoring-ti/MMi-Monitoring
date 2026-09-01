"""Tests Motor MMI M6 — discrepancias y EAM (sin red)."""

from datetime import date

from mmi.motor.discrepancies import (
    build_discrepancy_banner,
    detect_calibration_discrepancies,
    load_discrepancy_rules,
    process_discrepancies,
)
from mmi.motor.eam_history import build_eam_history_payload, match_work_orders_by_symptom


def test_load_discrepancy_rules():
    rules = load_discrepancy_rules()
    assert rules.get("calibration_max_days") == 365


def test_detect_calibration_pt882_overdue():
    rules = load_discrepancy_rules()
    disc = detect_calibration_discrepancies(
        "CTS-DCH-ENF",
        rules=rules,
        today=date(2026, 9, 1),
    )
    assert any("PT-882" in d["text"] for d in disc)
    assert disc[0]["rule"] == "calibration_overdue"


def test_build_eam_history_includes_wo88912():
    eam = build_eam_history_payload("CTS-DCH-ENF", "alta temperatura y caudal reducido")
    codes = [wo["wo_code"] for wo in eam["work_orders"]]
    assert "WO-88912" in codes


def test_match_work_orders_by_symptom():
    eam = build_eam_history_payload("CTS-DCH-ENF", "caída de caudal")
    assert eam["work_orders"][0]["wo_code"] == "WO-88912"


def test_process_discrepancies_merges_rules():
    disc, banner = process_discrepancies(
        [],
        asset_id="CTS-DCH-ENF",
        symptom="alta temperatura caudal",
        facts=[{"sensor": {"tag": "TE-401A"}, "limit": {"exceeded": True}}],
        hits=[],
        today=date(2026, 9, 1),
    )
    assert len(disc) >= 2
    assert banner["visible"] is True
    assert banner["count"] >= 2


def test_discrepancy_banner_empty():
    banner = build_discrepancy_banner([])
    assert banner["visible"] is False


def test_analyze_motor_includes_m6_fields():
    from unittest.mock import MagicMock

    from mmi.motor.analyze import analyze_motor

    engine = MagicMock()
    engine.search.return_value = []
    result = analyze_motor("CTS-DCH-ENF", "alta temperatura caudal", engine)
    assert result.discrepancy_banner.get("visible") is True
    assert "WO-88912" in [wo.get("wo_code") for wo in result.eam_history.get("work_orders", [])]
