"""Enlace remoto a carpeta de documentos (SharePoint / OneDrive) para revisión."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_PATH = Path("out/remote-source.json")

_ONEDRIVE = re.compile(
    r"(onedrive\.live\.com|1drv\.ms|sharepoint\.com|onedrive\.com)",
    re.I,
)


def detect_provider(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "sharepoint" in host:
        return "sharepoint"
    if "onedrive" in host or "1drv.ms" in host:
        return "onedrive"
    return "other"


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise ValueError("El enlace no puede estar vacío")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError("Enlace no válido — falta dominio")
    return url


def validate_remote_url(url: str) -> tuple[str, str]:
    """Devuelve (url normalizada, provider)."""
    normalized = normalize_url(url)
    provider = detect_provider(normalized)
    if provider == "other":
        # Permitir otros HTTPS pero avisar
        pass
    return normalized, provider


def load_remote_source(path: Path | None = None) -> dict | None:
    path = path or DEFAULT_PATH
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not data.get("url"):
        return None
    return data


def save_remote_source(
    url: str,
    *,
    label: str = "",
    path: Path | None = None,
    notes: str = "",
) -> dict:
    normalized, provider = validate_remote_url(url)
    payload = {
        "url": normalized,
        "label": (label or "").strip(),
        "provider": provider,
        "notes": (notes or "").strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path = path or DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
