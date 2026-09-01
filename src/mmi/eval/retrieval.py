"""Utilidades de evaluación de recuperación (golden set C3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mmi.search.engine import SearchResult


def load_golden_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        return data["cases"]
    raise ValueError("Golden set debe ser lista o {\"cases\": [...]}")


def _hit_text(hit: SearchResult) -> str:
    return " ".join(
        part
        for part in (
            hit.titulo or "",
            hit.content or "",
            hit.citation or "",
            hit.document_id or "",
            hit.tipo or "",
        )
        if part
    )


def is_relevant_hit(hit: SearchResult, spec: dict[str, Any]) -> bool:
    """Determina si un hit es relevante según especificación del golden set."""
    if not spec:
        return False

    text = _hit_text(hit).upper()
    titulo = (hit.titulo or "").upper()
    content = (hit.content or "").upper()

    tipo = (spec.get("tipo") or "").strip().lower()
    if tipo and (hit.tipo or "").strip().lower() != tipo:
        return False

    titulo_any = [str(t).upper() for t in (spec.get("titulo_any") or [])]
    content_any = [str(t).upper() for t in (spec.get("content_any") or [])]
    keywords_any = [str(t).upper() for t in (spec.get("keywords_any") or spec.get("expect_keywords") or [])]

    if titulo_any and not any(token in titulo for token in titulo_any):
        if not any(token in text for token in titulo_any):
            return False

    if content_any and not any(token in content for token in content_any):
        return False

    if keywords_any:
        return any(token in text for token in keywords_any)

    return bool(titulo_any or content_any or tipo)


def reciprocal_rank(hits: list[SearchResult], spec: dict[str, Any]) -> float:
    for i, hit in enumerate(hits, 1):
        if is_relevant_hit(hit, spec):
            return 1.0 / i
    return 0.0


def recall_at_k(hits: list[SearchResult], spec: dict[str, Any], k: int) -> float:
    return 1.0 if any(is_relevant_hit(h, spec) for h in hits[:k]) else 0.0


def precision_at_k(hits: list[SearchResult], spec: dict[str, Any], k: int) -> float:
    if k <= 0:
        return 0.0
    relevant = sum(1 for h in hits[:k] if is_relevant_hit(h, spec))
    return relevant / k


def case_relevant_spec(case: dict[str, Any]) -> dict[str, Any]:
    rel = dict(case.get("relevant") or {})
    if not rel and case.get("expect_keywords"):
        rel["keywords_any"] = case["expect_keywords"]
    return rel


def aggregate_metrics(rows: list[dict[str, Any]], *, k_values: list[int]) -> dict[str, Any]:
    total = len(rows)
    if not total:
        return {"total": 0}

    out: dict[str, Any] = {"total": total, "mrr": 0.0}
    for k in k_values:
        out[f"recall@{k}"] = 0.0
        out[f"precision@{k}"] = 0.0

    by_category: dict[str, dict[str, Any]] = {}

    for row in rows:
        cat = row.get("category") or "otro"
        bucket = by_category.setdefault(cat, {"count": 0, "mrr": 0.0})
        bucket["count"] += 1
        mrr = float(row.get("mrr") or 0.0)
        out["mrr"] += mrr
        bucket["mrr"] += mrr
        for k in k_values:
            rk = f"recall@{k}"
            pk = f"precision@{k}"
            out[rk] += float(row.get(rk) or 0.0)
            out[pk] += float(row.get(pk) or 0.0)
            bucket.setdefault(rk, 0.0)
            bucket.setdefault(pk, 0.0)
            bucket[rk] += float(row.get(rk) or 0.0)
            bucket[pk] += float(row.get(pk) or 0.0)

    out["mrr"] = round(out["mrr"] / total, 4)
    for k in k_values:
        out[f"recall@{k}"] = round(out[f"recall@{k}"] / total, 4)
        out[f"precision@{k}"] = round(out[f"precision@{k}"] / total, 4)

    for cat, bucket in by_category.items():
        n = bucket["count"]
        bucket["mrr"] = round(bucket["mrr"] / n, 4)
        for k in k_values:
            bucket[f"recall@{k}"] = round(bucket[f"recall@{k}"] / n, 4)
            bucket[f"precision@{k}"] = round(bucket[f"precision@{k}"] / n, 4)

    out["by_category"] = by_category
    return out
