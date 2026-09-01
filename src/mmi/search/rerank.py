"""Reranker léxico post-recuperación híbrida (C1)."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mmi.search.engine import SearchResult

_TAG_RE = re.compile(r"\b([A-Z]{1,4}-\d{2,5}[A-Z0-9]*)\b")
_DOC_CODE_RE = re.compile(
    r"\b(SGP[A-Z0-9-]+|SGPD[A-Z0-9-]+|FRMGS-\d+|GUIGS-\d+|PROGS-\d+|NCC-?\d+)\b",
    re.IGNORECASE,
)
_ACRONYM_RE = re.compile(r"\b(FMECA|GUIGS|PROGS|ATM|MRI|MSO|RCM|ENFR|ODS\d+|NCC)\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[a-z0-9áéíóúüñ]+", re.IGNORECASE)

_STOPWORDS = {
    "de",
    "la",
    "el",
    "en",
    "y",
    "a",
    "del",
    "los",
    "las",
    "un",
    "una",
    "por",
    "con",
    "para",
    "sistema",
    "activo",
    "ods1",
}


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS and len(t) > 2]


def extract_exact_tags(query: str) -> list[str]:
    tags: list[str] = []
    for pattern in (_TAG_RE, _DOC_CODE_RE, _ACRONYM_RE):
        tags.extend(m.group(1) if m.lastindex else m.group(0) for m in pattern.finditer(query or ""))
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        key = tag.upper()
        if key not in seen:
            seen.add(key)
            out.append(tag)
    return out


def lexical_overlap(query: str, text: str) -> float:
    q_tokens = tokenize(query)
    if not q_tokens:
        return 0.0
    t_set = set(tokenize(text))
    hits = sum(1 for t in q_tokens if t in t_set)
    return hits / len(q_tokens)


def title_phrase_boost(query: str, titulo: str | None) -> float:
    if not titulo:
        return 0.0
    title_l = titulo.lower()
    q_tokens = tokenize(query)
    if len(q_tokens) < 2:
        return 0.0
    joined = " ".join(q_tokens)
    if joined[:24] in title_l:
        return 0.25
    consecutive = 0
    best = 0
    for tok in q_tokens:
        if tok in title_l:
            consecutive += 1
            best = max(best, consecutive)
        else:
            consecutive = 0
    if best >= 3:
        return 0.2
    if best >= 2:
        return 0.1
    return 0.0


def exact_tag_boost(query: str, result: SearchResult) -> float:
    haystack = f"{result.titulo or ''} {result.content or ''} {result.citation or ''}".upper()
    boost = 0.0
    for tag in extract_exact_tags(query):
        if tag.upper() in haystack:
            boost += 0.18
    query_u = (query or "").upper()
    for code in result.asset_codes or []:
        if code and code.upper() in query_u:
            boost += 0.22
    return boost


def compute_rerank_score(query: str, result: SearchResult, *, base_weight: float = 0.35) -> float:
    text = f"{result.titulo or ''} {result.content or ''}"
    overlap = lexical_overlap(query, text)
    tag_boost = min(exact_tag_boost(query, result), 0.8)
    title_boost = title_phrase_boost(query, result.titulo)
    return (
        float(result.score) * base_weight
        + overlap * 0.45
        + tag_boost
        + title_boost
    )


def rerank_results(query: str, results: list[SearchResult]) -> list[SearchResult]:
    """Reordena candidatos tras recuperación híbrida."""
    if not results:
        return []
    scored: list[tuple[float, SearchResult]] = []
    for result in results:
        new_score = compute_rerank_score(query, result)
        row = replace(result, score=new_score)
        row.score = new_score
        scored.append((new_score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored]
