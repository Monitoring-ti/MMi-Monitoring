"""Sesión Motor MMI para detalles bajo demanda."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from time import time
from typing import Any

from mmi.search.engine import SearchResult


@dataclass
class MotorSession:
    asset_id: str
    symptom: str
    window: str
    hits: list[SearchResult]
    analysis: dict[str, Any]
    references: list[dict]
    model: str
    created: float = field(default_factory=time)


class MotorSessionStore:
    def __init__(self, *, max_items: int = 30, ttl_sec: int = 1800) -> None:
        self._sessions: dict[str, MotorSession] = {}
        self.max_items = max_items
        self.ttl_sec = ttl_sec

    def put(self, session: MotorSession) -> str:
        self._purge()
        motor_id = secrets.token_urlsafe(12)
        self._sessions[motor_id] = session
        while len(self._sessions) > self.max_items:
            oldest = min(self._sessions, key=lambda k: self._sessions[k].created)
            del self._sessions[oldest]
        return motor_id

    def get(self, motor_id: str) -> MotorSession | None:
        self._purge()
        session = self._sessions.get(motor_id)
        if session is None:
            return None
        if time() - session.created > self.ttl_sec:
            del self._sessions[motor_id]
            return None
        return session

    def _purge(self) -> None:
        now = time()
        expired = [mid for mid, s in self._sessions.items() if now - s.created > self.ttl_sec]
        for mid in expired:
            del self._sessions[mid]
