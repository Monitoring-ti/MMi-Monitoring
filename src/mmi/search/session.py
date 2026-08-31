"""Caché en memoria de sesiones RAG para cargar detalles bajo demanda."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from time import time

from mmi.search.engine import SearchResult


@dataclass
class AskSession:
    query: str
    hits: list[SearchResult]
    cited_indices: list[int]
    references: list[dict]
    created: float = field(default_factory=time)


class AskSessionStore:
    def __init__(self, *, max_items: int = 40, ttl_sec: int = 1800) -> None:
        self._sessions: dict[str, AskSession] = {}
        self.max_items = max_items
        self.ttl_sec = ttl_sec

    def put(self, session: AskSession) -> str:
        self._purge()
        session_id = secrets.token_urlsafe(12)
        self._sessions[session_id] = session
        while len(self._sessions) > self.max_items:
            oldest = min(self._sessions, key=lambda k: self._sessions[k].created)
            del self._sessions[oldest]
        return session_id

    def get(self, session_id: str) -> AskSession | None:
        self._purge()
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if time() - session.created > self.ttl_sec:
            del self._sessions[session_id]
            return None
        return session

    def _purge(self) -> None:
        now = time()
        expired = [sid for sid, s in self._sessions.items() if now - s.created > self.ttl_sec]
        for sid in expired:
            del self._sessions[sid]
