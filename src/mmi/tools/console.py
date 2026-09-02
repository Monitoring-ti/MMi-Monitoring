"""Utilidades de consola para CLIs MMI (Windows cp1252-safe)."""

from __future__ import annotations

import sys


def configure_stdout_utf8() -> None:
    """Evita UnicodeEncodeError al imprimir flechas/unicode en Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
