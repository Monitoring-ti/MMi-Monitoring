"""Payloads JSON para endpoints RAG."""

from __future__ import annotations

from mmi.search.session import AskSession


def ask_payload(result, session_id: str, elapsed_ms: int) -> dict:
    return {
        "query": result.query,
        "ask_id": session_id,
        "answer": result.answer,
        "model": result.model,
        "evidence_count": result.evidence_count,
        "cited_count": len(result.cited_indices),
        "cited_indices": result.cited_indices,
        "elapsed_ms": elapsed_ms,
    }


def ask_details_payload(session: AskSession, section: str, result_dict) -> dict:
    if section == "references":
        return {"section": section, "references": session.references}
    if section == "evidence":
        return {
            "section": section,
            "cited_indices": session.cited_indices,
            "results": [result_dict(h) for h in session.hits],
        }
    raise ValueError(f"Sección desconocida: {section}")
