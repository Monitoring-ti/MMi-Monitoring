"""Modo de despliegue MMI (development | vitrina)."""

from __future__ import annotations

import os


def get_deploy_mode() -> str:
    return (os.getenv("MMI_DEPLOY_MODE") or "development").strip().lower()


def is_vitrina() -> bool:
    return get_deploy_mode() == "vitrina"
