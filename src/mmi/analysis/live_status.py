"""Snapshot ligero de ingesta en curso (logs + JSON en out/)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PHASE0_LINE = re.compile(
    r"^\s*\[(OK|SKIP|MISSING|REVIEW|REJECT|[A-Z]+)\]\s+(.+?)(?:\s+—|$)",
    re.MULTILINE,
)
_INDEX_LINE = re.compile(
    r"^\[(\d+)/(\d+)\]\s+(\S+)\s+(\d+)\s+ch\s+(.+)$",
    re.MULTILINE,
)


def _read_tail(path: Path, max_bytes: int = 96_000) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _last_phase0_activity(tail: str) -> dict[str, Any] | None:
    matches = list(_PHASE0_LINE.finditer(tail))
    if not matches:
        return None
    m = matches[-1]
    return {
        "mark": m.group(1),
        "file": m.group(2).strip()[:120],
    }


def _last_index_activity(tail: str) -> dict[str, Any] | None:
    matches = list(_INDEX_LINE.finditer(tail))
    if not matches:
        return None
    m = matches[-1]
    return {
        "current": int(m.group(1)),
        "total": int(m.group(2)),
        "estado": m.group(3),
        "chunks": int(m.group(4)),
        "file": m.group(5).strip()[:120],
    }


def _count_extracts(extract_root: Path) -> int:
    if not extract_root.exists():
        return 0
    n = 0
    for child in extract_root.iterdir():
        if child.is_dir() and (child / "extracted.json").exists():
            n += 1
    return n


def collect_live_snapshot(out_dir: Path | None = None) -> dict[str, Any]:
    base = out_dir or Path("out")
    snapshot: dict[str, Any] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "summary": {},
        "index_summary": {},
        "dashboard_generated_at": None,
        "phase0": {},
        "index": {},
        "extract_count": 0,
    }

    status_path = base / "analysis-status.json"
    if status_path.exists():
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
            snapshot["summary"] = data.get("summary") or {}
            snapshot["index_summary"] = data.get("index_summary") or {}
            snapshot["dashboard_generated_at"] = data.get("generated_at")
        except (OSError, json.JSONDecodeError):
            pass

    idx_path = base / "index-corpus-summary.json"
    if idx_path.exists():
        try:
            idx = json.loads(idx_path.read_text(encoding="utf-8"))
            if idx.get("stats"):
                snapshot["index_summary"] = idx["stats"]
            snapshot["index"]["updated_at"] = idx.get("updated_at")
            snapshot["index"]["progress"] = idx.get("progress")
        except (OSError, json.JSONDecodeError):
            pass

    phase0_log = base / "ods1-phase0.log"
    if phase0_log.exists():
        tail = _read_tail(phase0_log)
        act = _last_phase0_activity(tail)
        if act:
            snapshot["phase0"]["activity"] = act
        snapshot["phase0"]["log_mtime"] = datetime.fromtimestamp(
            phase0_log.stat().st_mtime, tz=timezone.utc
        ).isoformat()

    index_log = base / "index-corpus.log"
    if index_log.exists():
        tail = _read_tail(index_log)
        act = _last_index_activity(tail)
        if act:
            snapshot["index"]["activity"] = act
        snapshot["index"]["log_mtime"] = datetime.fromtimestamp(
            index_log.stat().st_mtime, tz=timezone.utc
        ).isoformat()

    from mmi.analysis.status import load_token_summary

    snapshot["token_summary"] = load_token_summary(base)

    extract_root = base / "ods1-extract"
    snapshot["extract_count"] = _count_extracts(extract_root)

    return snapshot


def append_ingestion_log(out_dir: Path, log_name: str, line: str) -> None:
    path = Path(out_dir) / log_name
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")
    except OSError:
        pass  # log puede estar bloqueado por Tee-Object u otro proceso
