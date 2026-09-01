"""Extracción de límites OEM / alarma desde texto de chunks documentales."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_TAG_RE = re.compile(r"\b([A-Z]{1,3}-\d{2,4}[A-Z]?)\b")

_LIMIT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "max_temp",
        re.compile(
            r"(?:m[aá]x(?:ima)?|l[ií]mite|alarma|max(?:imum)?\s*temp(?:eratura)?)"
            r"[^.\n]{0,40}?(\d+(?:[.,]\d+)?)\s*°?\s*C\b",
            re.IGNORECASE,
        ),
    ),
    (
        "max_vibration",
        re.compile(
            r"(?:m[aá]x(?:ima)?|l[ií]mite|alarma|vibraci[oó]n)"
            r"[^.\n]{0,40}?(\d+(?:[.,]\d+)?)\s*mm\s*/\s*s\b",
            re.IGNORECASE,
        ),
    ),
    (
        "nominal_flow",
        re.compile(
            r"(?:nominal|caudal\s*(?:de\s*)?dise[nñ]o|setpoint)"
            r"[^.\n]{0,40}?(\d+(?:[.,]\d+)?)\s*L\s*/\s*min\b",
            re.IGNORECASE,
        ),
    ),
    (
        "min_flow",
        re.compile(
            r"(?:m[ií]n(?:ima)?|l[ií]mite\s*bajo|alarma\s*baja)"
            r"[^.\n]{0,40}?(\d+(?:[.,]\d+)?)\s*L\s*/\s*min\b",
            re.IGNORECASE,
        ),
    ),
    (
        "generic_limit",
        re.compile(
            r"(?:l[ií]mite|alarma|umbral)"
            r"[^.\n]{0,30}?(\d+(?:[.,]\d+)?)\s*(°C|mm/s|L/min|bar|kPa)\b",
            re.IGNORECASE,
        ),
    ),
]


@dataclass(frozen=True)
class OemLimit:
    kind: str
    value: float
    unit: str
    tag: str | None = None
    context: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "unit": self.unit,
            "tag": self.tag,
            "context": self.context,
        }


def _parse_number(raw: str) -> float:
    return float(raw.replace(",", "."))


def _unit_for_kind(kind: str, captured_unit: str | None = None) -> str:
    if captured_unit:
        return captured_unit.replace(" ", "")
    if kind == "max_temp":
        return "°C"
    if kind == "max_vibration":
        return "mm/s"
    if kind in {"nominal_flow", "min_flow"}:
        return "L/min"
    return captured_unit or ""


def _nearby_tag(text: str, start: int, end: int) -> str | None:
    window = text[max(0, start - 80) : min(len(text), end + 80)]
    tags = _TAG_RE.findall(window)
    return tags[0] if tags else None


def extract_limits_from_text(text: str, *, tag: str | None = None) -> list[OemLimit]:
    """Extrae límites OEM/alarma de un fragmento de documento."""
    if not text:
        return []
    found: list[OemLimit] = []
    seen: set[tuple[str, float, str]] = set()

    for kind, pattern in _LIMIT_PATTERNS:
        for match in pattern.finditer(text):
            if kind == "generic_limit":
                value = _parse_number(match.group(1))
                unit = match.group(2)
            else:
                value = _parse_number(match.group(1))
                unit = _unit_for_kind(kind)
            nearby = _nearby_tag(text, match.start(), match.end())
            resolved_tag = tag or nearby
            key = (kind, value, unit)
            if key in seen:
                continue
            seen.add(key)
            context = text[max(0, match.start() - 20) : min(len(text), match.end() + 40)].strip()
            found.append(
                OemLimit(
                    kind=kind,
                    value=value,
                    unit=unit,
                    tag=resolved_tag,
                    context=context,
                )
            )
    return found


def extract_limits_from_hits(
    hits: list[Any],
    *,
    tags: list[str] | None = None,
) -> list[tuple[int, OemLimit]]:
    """Extrae límites de hits de búsqueda; retorna (citation_index, limit)."""
    tag_set = {t.upper() for t in (tags or [])}
    results: list[tuple[int, OemLimit]] = []
    for i, hit in enumerate(hits, 1):
        content = getattr(hit, "content", "") or ""
        if tag_set:
            if not any(t in content.upper() for t in tag_set):
                limits = extract_limits_from_text(content)
            else:
                limits = []
                for tag in tag_set:
                    if tag in content.upper():
                        limits.extend(extract_limits_from_text(content, tag=tag))
                if not limits:
                    limits = extract_limits_from_text(content)
        else:
            limits = extract_limits_from_text(content)
        for lim in limits:
            results.append((i, lim))
    return results
