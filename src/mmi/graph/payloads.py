"""Payloads API del Mapa de Conocimiento."""

from __future__ import annotations

from typing import Any

from mmi.graph.models import GraphNode, GraphPayload
from mmi.search.answer import AnswerResult, generate_answer
from mmi.search.engine import SearchResult


def graph_payload_dict(payload: GraphPayload, *, elapsed_ms: int = 0) -> dict[str, Any]:
    data = payload.to_dict()
    data["count"] = {"nodes": len(payload.nodes), "edges": len(payload.edges)}
    data["conflict_count"] = len(payload.conflicts)
    data["elapsed_ms"] = elapsed_ms
    return data


def node_payload_dict(node: GraphNode) -> dict[str, Any]:
    return node.to_dict()


def graph_ask_payload(result: AnswerResult, *, elapsed_ms: int = 0) -> dict[str, Any]:
    return {
        "query": result.query,
        "answer": result.answer,
        "model": result.model,
        "references": result.references,
        "citations": result.cited_indices,
        "conflicts": result.conflicts,
        "conflict_banner": result.conflict_banner,
        "evidence_count": result.evidence_count,
        "elapsed_ms": elapsed_ms,
    }


def ask_on_hits(query: str, hits: list[SearchResult], *, limit: int = 8) -> AnswerResult:
    trimmed = hits[:limit]
    return generate_answer(query, trimmed)
