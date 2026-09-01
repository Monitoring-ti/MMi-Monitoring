"""Rutas API compartidas (búsqueda, RAG, motor) para serve_local y out_handler."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from mmi.motor.analyze import analyze_motor
from mmi.motor.payloads import motor_analyze_payload, motor_details_payload
from mmi.motor.session import MotorSession, MotorSessionStore
from mmi.search.answer import ask
from mmi.search.api_payloads import ask_details_payload, ask_payload
from mmi.search.engine import HybridSearchEngine
from mmi.search.session import AskSession, AskSessionStore
from mmi.tools.search_cli import _result_dict

MOTOR_API_VERSION = "m6"


class JsonHandler(Protocol):
    def _send_json(self, data: dict, status: int = 200) -> None: ...


@dataclass
class ApiContext:
    tenant_slug: str
    out_dir: Path
    sessions: AskSessionStore = field(default_factory=AskSessionStore)
    motor_sessions: MotorSessionStore = field(default_factory=MotorSessionStore)
    _engine: HybridSearchEngine | None = field(default=None, repr=False)

    @property
    def engine(self) -> HybridSearchEngine:
        if self._engine is None:
            self._engine = HybridSearchEngine(tenant_slug=self.tenant_slug)
        return self._engine


def motor_health_payload() -> dict[str, Any]:
    return {"ok": True, "motor_api": True, "version": MOTOR_API_VERSION}


def handle_get_api(path: str, handler: JsonHandler, ctx: ApiContext) -> bool:
    if path == "/api/motor/health":
        handler._send_json(motor_health_payload())
        return True
    return False


def handle_post_api(path: str, data: dict[str, Any], handler: JsonHandler, ctx: ApiContext) -> bool:
    if path not in {
        "/api/search",
        "/api/ask",
        "/api/ask-details",
        "/api/motor/analyze",
        "/api/motor/details",
    }:
        return False

    t0 = time.perf_counter()

    if path == "/api/motor/details":
        motor_id = (data.get("motor_id") or "").strip()
        section = (data.get("section") or "").strip()
        session = ctx.motor_sessions.get(motor_id)
        if session is None:
            handler._send_json({"error": "Sesión motor expirada o inválida"}, status=404)
            return True
        payload = motor_details_payload(session, section, result_dict=_result_dict)
        payload["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        handler._send_json(payload)
        return True

    if path == "/api/motor/analyze":
        asset_id = (data.get("asset_id") or "").strip()
        symptom = (data.get("symptom") or "").strip()
        window = (data.get("window") or "24h").strip()
        limit = int(data.get("limit") or 8)
        if not asset_id or not symptom:
            handler._send_json({"error": "Se requiere asset_id y symptom"}, status=400)
            return True
        try:
            result = analyze_motor(
                asset_id,
                symptom,
                ctx.engine,
                window=window,
                limit=limit,
                tenant_slug=ctx.tenant_slug,
            )
        except Exception as exc:  # noqa: BLE001
            handler._send_json({"error": str(exc)}, status=500)
            return True
        analysis_snapshot = {
            "hypotheses": result.hypotheses,
            "verified_facts": result.verified_facts,
            "discrepancies": result.discrepancies,
            "discrepancy_banner": result.discrepancy_banner,
            "eam_history": result.eam_history,
        }
        motor_id = ctx.motor_sessions.put(
            MotorSession(
                asset_id=asset_id,
                symptom=symptom,
                window=window,
                hits=result.hits,
                analysis=analysis_snapshot,
                references=result.references,
                model=result.model,
            )
        )
        payload = motor_analyze_payload(result, motor_id, int((time.perf_counter() - t0) * 1000))
        handler._send_json(payload)
        return True

    if path == "/api/ask-details":
        session_id = (data.get("ask_id") or "").strip()
        section = (data.get("section") or "").strip()
        session = ctx.sessions.get(session_id)
        if session is None:
            handler._send_json({"error": "Sesión expirada o inválida"}, status=404)
            return True
        payload = ask_details_payload(session, section, _result_dict)
        payload["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        handler._send_json(payload)
        return True

    query = (data.get("query") or "").strip()
    limit = int(data.get("limit") or 6)

    if path == "/api/search":
        hits = ctx.engine.search(query, limit=limit)
        handler._send_json(
            {
                "query": query,
                "count": len(hits),
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                "results": [_result_dict(r) for r in hits],
            }
        )
        return True

    result = ask(query, ctx.engine, limit=limit)
    session_id = ctx.sessions.put(
        AskSession(
            query=result.query,
            hits=result.hits,
            cited_indices=result.cited_indices,
            references=result.references,
            conflicts=result.conflicts,
        )
    )
    handler._send_json(
        ask_payload(result, session_id, int((time.perf_counter() - t0) * 1000))
    )
    return True
