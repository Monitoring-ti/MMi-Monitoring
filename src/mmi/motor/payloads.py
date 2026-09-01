"""Payloads JSON para API Motor MMI."""

from __future__ import annotations

from typing import Any, Callable

from mmi.motor.analyze import MotorAnalysisResult
from mmi.motor.export_meta import build_export_meta
from mmi.motor.hypotheses import INFERENCE_DISCLAIMER
from mmi.motor.session import MotorSession


def motor_analyze_payload(result: MotorAnalysisResult, motor_id: str, elapsed_ms: int) -> dict[str, Any]:
    export_meta = build_export_meta(result, motor_id)
    return {
        "motor_id": motor_id,
        "asset": result.asset,
        "symptom": result.symptom,
        "window": result.window,
        "diagnosis": result.diagnosis,
        "verified_facts": result.verified_facts,
        "hypotheses": result.hypotheses,
        "inference_disclaimer": INFERENCE_DISCLAIMER,
        "physical_checks": result.physical_checks,
        "discrepancies": result.discrepancies,
        "discrepancy_banner": result.discrepancy_banner,
        "eam_history": result.eam_history,
        "sources_preview": result.sources_preview,
        "model": result.model,
        "evidence_count": len(result.hits),
        "elapsed_ms": elapsed_ms,
        "export_meta": export_meta,
    }


def motor_details_payload(
    session: MotorSession,
    section: str,
    *,
    result_dict: Callable | None = None,
) -> dict[str, Any]:
    if section == "sources":
        return {"section": section, "references": session.references}
    if section == "raw_evidence":
        if result_dict is None:
            raise ValueError("result_dict requerido para raw_evidence")
        return {
            "section": section,
            "results": [result_dict(h) for h in session.hits],
        }
    if section == "hypotheses_full":
        return {
            "section": section,
            "hypotheses": session.analysis.get("hypotheses") or [],
            "verified_facts": session.analysis.get("verified_facts") or [],
        }
    if section == "eam_history":
        return {
            "section": section,
            "eam_history": session.analysis.get("eam_history") or {},
        }
    if section == "discrepancies_full":
        return {
            "section": section,
            "discrepancies": session.analysis.get("discrepancies") or [],
            "discrepancy_banner": session.analysis.get("discrepancy_banner") or {},
        }
    raise ValueError(f"Sección desconocida: {section}")
