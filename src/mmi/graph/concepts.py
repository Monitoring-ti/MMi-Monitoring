"""Extracción de nodos concepto (FMECA / RPN) para el grafo."""

from __future__ import annotations

import re
from typing import Any

from mmi.graph.models import GraphEdge, GraphNode
from mmi.search.conflicts import detect_conflicts, infer_document_key
from mmi.search.engine import SearchResult

_FALLA_RE = re.compile(
    r"modo\s+de\s+falla[:\s\-]+([^\n.;]{4,72})",
    re.IGNORECASE,
)
_EFECTO_RE = re.compile(
    r"efecto[s]?\s+(?:del\s+)?(?:modo\s+de\s+)?falla[:\s\-]+([^\n.;]{4,72})",
    re.IGNORECASE,
)
_RPN_RE = re.compile(r"\bRPN\s*[:=]?\s*(\d+)\b", re.IGNORECASE)
_FMECA_HINT = re.compile(r"\bFMECA\b", re.IGNORECASE)


def _slug(text: str, *, max_len: int = 48) -> str:
    s = re.sub(r"[^\w\s\-]", "", text.strip().lower())
    s = re.sub(r"\s+", "-", s).strip("-")
    return s[:max_len] or "concepto"


def _concept_id(kind: str, label: str) -> str:
    return f"concept:{kind}:{_slug(label)}"


def extract_concepts_from_hit(hit: SearchResult) -> list[tuple[str, str, str]]:
    """(kind, label, concept_type)"""
    text = f"{hit.titulo or ''}\n{hit.content or ''}"
    if not _FMECA_HINT.search(text) and (hit.tipo or "").lower() not in {"tabla", "guia", "presentacion"}:
        return []

    found: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    for pattern, ctype in ((_FALLA_RE, "fmeca_falla"), (_EFECTO_RE, "fmeca_efecto")):
        for match in pattern.finditer(text):
            label = match.group(1).strip()
            if len(label) < 4:
                continue
            key = _slug(label)
            if key in seen:
                continue
            seen.add(key)
            found.append((key, label[:72], ctype))

    for match in _RPN_RE.finditer(text):
        val = match.group(1)
        label = f"RPN {val}"
        key = f"rpn-{val}"
        if key in seen:
            continue
        seen.add(key)
        found.append((key, label, "rpn"))

    return found


def concept_node(label: str, *, concept_type: str) -> GraphNode:
    return GraphNode(
        id=_concept_id(concept_type, label),
        kind="concept",
        label=label[:72],
        score=0.0,
        meta={"concept_type": concept_type},
    )


def attach_concepts(
    hits: list[SearchResult],
    nodes: dict[str, GraphNode],
    edges: dict[str, GraphEdge],
    *,
    chunk_id_for,
) -> None:
    for hit in hits:
        chunk_id = chunk_id_for(hit.point_id)
        if chunk_id not in nodes:
            continue
        for _key, label, ctype in extract_concepts_from_hit(hit):
            concept = concept_node(label, concept_type=ctype)
            nodes[concept.id] = concept
            eid = f"mentions_concept:{chunk_id}->{concept.id}"
            edges[eid] = GraphEdge(
                id=eid,
                source=chunk_id,
                target=concept.id,
                kind="co_occurs",
                weight=0.75,
            )


def attach_conflict_edges(
    hits: list[SearchResult],
    nodes: dict[str, GraphNode],
    edges: dict[str, GraphEdge],
    *,
    chunk_id_for,
) -> list[dict[str, Any]]:
    conflicts = detect_conflicts(hits)
    if not conflicts:
        return conflicts

    by_key: dict[str, list[SearchResult]] = {}
    for hit in hits:
        by_key.setdefault(infer_document_key(hit), []).append(hit)

    for hit in hits:
        cid = chunk_id_for(hit.point_id)
        if cid in nodes:
            nodes[cid].meta["has_conflict"] = False

    for row in conflicts:
        if row.get("kind") != "version":
            continue
        doc_key = row.get("document_key") or ""
        group = by_key.get(doc_key, [])
        if len(group) < 2:
            continue
        chunk_ids = [chunk_id_for(h.point_id) for h in group if chunk_id_for(h.point_id) in nodes]
        for i, a in enumerate(chunk_ids):
            nodes[a].meta["has_conflict"] = True
            for b in chunk_ids[i + 1 :]:
                nodes[b].meta["has_conflict"] = True
                eid = f"conflicts_with:{a}->{b}"
                edges[eid] = GraphEdge(
                    id=eid,
                    source=a,
                    target=b,
                    kind="conflicts_with",
                    weight=1.0,
                )

    return conflicts
