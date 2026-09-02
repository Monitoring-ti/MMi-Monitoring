"""Modo de despliegue MMI (development | vitrina)."""

from __future__ import annotations

import os


def get_deploy_mode() -> str:
    mode = (os.getenv("MMI_DEPLOY_MODE") or "development").strip().lower()
    if os.getenv("RAILWAY_ENVIRONMENT") and mode == "development":
        return "vitrina"
    return mode


def is_vitrina() -> bool:
    return get_deploy_mode() == "vitrina"
