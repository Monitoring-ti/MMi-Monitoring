"""Controles de acceso para vitrina / Railway."""

from __future__ import annotations

import base64
import os
from typing import Any


LIVE_QUERY_PATHS = frozenset({"/api/search", "/api/ask", "/api/ask-details"})

# Healthcheck Railway — sin auth para no tumbar el deploy.
AUTH_EXEMPT_PATHS = frozenset({"/api/motor/health"})


def live_queries_enabled() -> bool:
    """Consultas al corpus en vivo. En Railway/vitrina default OFF."""
    raw = (os.getenv("MMI_VITRINA_LIVE_QUERIES") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    # Sin variable: local OK; Railway bloqueado por defecto.
    return not bool(os.getenv("RAILWAY_ENVIRONMENT"))


def basic_auth_credentials() -> tuple[str, str] | None:
    user = (os.getenv("MMI_BASIC_AUTH_USER") or "").strip()
    password = os.getenv("MMI_BASIC_AUTH_PASSWORD") or ""
    if user and password:
        return user, password
    return None


def basic_auth_required() -> bool:
    return basic_auth_credentials() is not None


def check_basic_auth(authorization_header: str | None) -> bool:
    creds = basic_auth_credentials()
    if creds is None:
        return True
    if not authorization_header or not authorization_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(authorization_header[6:].strip()).decode("utf-8")
        user, _, password = decoded.partition(":")
    except Exception:  # noqa: BLE001
        return False
    expected_user, expected_password = creds
    return user == expected_user and password == expected_password


def live_query_block_payload() -> dict[str, Any]:
    return {
        "error": "Consultas al corpus bloqueadas temporalmente.",
        "hint": "Definir MMI_VITRINA_LIVE_QUERIES=1 solo con Basic Auth activo (MMI_BASIC_AUTH_USER/PASSWORD).",
        "locked": True,
    }
