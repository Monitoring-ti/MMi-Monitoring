"""Detección de contradicciones multi-versión (C2)."""

from __future__ import annotations

import re
from typing import Any

from mmi.search.engine import SearchResult

_REV_RE = re.compile(r"\b(rev\.?|versi[oó]n|version)\s*[a-z0-9.]+\b", re.IGNORECASE)
_TEMP_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*°?\s*C\b", re.IGNORECASE)
_RPN_RE = re.compile(r"\bRPN\s*[:=]?\s*(\d+)\b", re.IGNORECASE)
_CRIT_RE = re.compile(r"\bcriticidad\s*[:=]?\s*(\d+)\b", re.IGNORECASE)
_LIMIT_RE = re.compile(
    r"(?:l[ií]mite|m[aá]x(?:ima)?|alarma|umbral)\s*[^.\n]{0,25}?(\d+(?:[.,]\d+)?)\s*°?\s*C\b",
    re.IGNORECASE,
)


def infer_document_key(hit: SearchResult) -> str:
    if getattr(hit, "document_key", None):
        return str(hit.document_key).strip()
    base = (hit.titulo or hit.citation or hit.document_id or "").strip()
    base = _REV_RE.sub("", base)
    base = re.sub(r"\s+", " ", base).strip().upper()
    return base[:160] or hit.document_id or "unknown"


def _parse_num(raw: str) -> float:
    return float(raw.replace(",", "."))


def _extract_metrics(text: str) -> list[tuple[str, float, str]]:
    """(kind, value, snippet)"""
    found: list[tuple[str, float, str]] = []
    for kind, pattern in (
        ("temp_c", _TEMP_RE),
        ("rpn", _RPN_RE),
        ("criticidad", _CRIT_RE),
        ("limit_c", _LIMIT_RE),
    ):
        for match in pattern.finditer(text or ""):
            val = _parse_num(match.group(1))
            snippet = text[max(0, match.start() - 15) : min(len(text), match.end() + 15)].strip()
            found.append((kind, val, snippet))
    return found


def detect_version_conflicts(hits: list[SearchResult]) -> list[dict[str, Any]]:
    by_key: dict[str, list[SearchResult]] = {}
    for hit in hits:
        key = infer_document_key(hit)
        by_key.setdefault(key, []).append(hit)

    conflicts: list[dict[str, Any]] = []
    for doc_key, group in by_key.items():
        versions = sorted({(h.version_label or "").strip() for h in group if (h.version_label or "").strip()})
        if len(versions) < 2:
            continue
        titles = [h.titulo or h.citation or doc_key for h in group[:3]]
        conflicts.append(
            {
                "kind": "version",
                "severity": "warn",
                "document_key": doc_key,
                "text": (
                    f"Versiones distintas para el mismo documento ({doc_key}): "
                    f"{', '.join(versions)}"
                ),
                "versions": versions,
                "sources": titles,
            }
        )
    return conflicts


def detect_numeric_conflicts(hits: list[SearchResult], *, tolerance_pct: float = 0.02) -> list[dict[str, Any]]:
    """Contradicciones numéricas entre chunks recuperados (misma familia doc)."""
    buckets: dict[tuple[str, str], list[tuple[float, str, SearchResult]]] = {}
    for hit in hits:
        text = f"{hit.titulo or ''} {hit.content or ''}"
        doc_key = infer_document_key(hit)
        for kind, value, snippet in _extract_metrics(text):
            buckets.setdefault((doc_key, kind), []).append((value, snippet, hit))

    conflicts: list[dict[str, Any]] = []
    for (doc_key, kind), rows in buckets.items():
        values = [v for v, _, _ in rows]
        if len(values) < 2:
            continue
        vmin, vmax = min(values), max(values)
        if vmin == vmax:
            continue
        if vmax > 0 and (vmax - vmin) / vmax <= tolerance_pct:
            continue
        label = {"temp_c": "°C", "limit_c": "límite °C", "rpn": "RPN", "criticidad": "criticidad"}.get(kind, kind)
        conflicts.append(
            {
                "kind": "numeric",
                "severity": "warn",
                "document_key": doc_key,
                "metric": kind,
                "text": (
                    f"Valores {label} inconsistentes en evidencia ({doc_key}): "
                    f"{vmin:g} vs {vmax:g}"
                ),
                "values": sorted(set(values)),
                "sources": [h.titulo or h.citation for _, _, h in rows[:3]],
            }
        )
    return conflicts


def detect_pptx_rpn_conflicts(hits: list[SearchResult]) -> list[dict[str, Any]]:
    pptx_hits = [h for h in hits if (h.tipo or "").lower() in {"presentacion", "presentación"}]
    if len(pptx_hits) < 2:
        return []

    rpn_by_slide: dict[str, set[int]] = {}
    for hit in pptx_hits:
        section = (hit.section_path or hit.titulo or "slide").strip()
        text = hit.content or ""
        rpns = {int(m.group(1)) for m in _RPN_RE.finditer(text)}
        if rpns:
            rpn_by_slide.setdefault(section, set()).update(rpns)

    conflicts: list[dict[str, Any]] = []
    all_rpns: set[int] = set()
    for rpns in rpn_by_slide.values():
        all_rpns |= rpns
    if len(all_rpns) > 1:
        conflicts.append(
            {
                "kind": "pptx_rpn",
                "severity": "info",
                "text": (
                    "Presentación: RPN/criticidad distinta entre diapositivas recuperadas "
                    f"({min(all_rpns)} – {max(all_rpns)})"
                ),
                "values": sorted(all_rpns),
                "slides": list(rpn_by_slide.keys())[:5],
            }
        )
    return conflicts


def detect_superseded_leak(hits: list[SearchResult]) -> list[dict[str, Any]]:
    leaked = [
        h
        for h in hits
        if (getattr(h, "version_status", None) or "").lower() in {"superseded", "indexed"}
        or getattr(h, "is_current", True) is False
    ]
    if not leaked:
        return []
    titles = [h.titulo or h.citation or h.document_id for h in leaked[:3]]
    return [
        {
            "kind": "superseded",
            "severity": "warn",
            "text": (
                "Evidencia incluye documentos no vigentes (superseded/no current). "
                "Verificar filtro de versión activa."
            ),
            "sources": titles,
        }
    ]


def detect_conflicts(hits: list[SearchResult]) -> list[dict[str, Any]]:
    """Pipeline C2: versiones, numérico, PPTX, superseded."""
    if not hits:
        return []

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in (
        detect_superseded_leak(hits),
        detect_version_conflicts(hits),
        detect_numeric_conflicts(hits),
        detect_pptx_rpn_conflicts(hits),
    ):
        for row in group:
            key = row.get("text", "")
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)

    merged.sort(key=lambda r: (0 if r.get("severity") == "warn" else 1, r.get("kind", "")))
    return merged


def conflict_banner(conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    if not conflicts:
        return {"visible": False, "count": 0, "message": ""}
    warn = sum(1 for c in conflicts if c.get("severity") == "warn")
    count = len(conflicts)
    return {
        "visible": True,
        "count": count,
        "severity": "warn" if warn else "info",
        "message": (
            f"{count} conflicto{'s' if count != 1 else ''} documental detectado"
            f"{'s' if count != 1 else ''} — requiere validación humana"
        ),
    }
