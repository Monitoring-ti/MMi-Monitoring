"""Modelos del grafo de conocimiento."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

NodeKind = Literal["chunk", "document", "asset", "concept"]
EdgeKind = Literal[
    "similar_to",
    "part_of",
    "mentions_asset",
    "same_document_key",
    "co_occurs",
    "conflicts_with",
]
ViewMode = Literal["global", "documents", "concepts"]


@dataclass
class GraphNode:
    id: str
    kind: NodeKind
    label: str
    score: float = 0.0
    document_id: str | None = None
    point_id: str | None = None
    tipo: str | None = None
    dominio: str | None = None
    document_key: str | None = None
    version_label: str | None = None
    citation: str | None = None
    content_preview: str = ""
    asset_codes: list[str] = field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    id: str
    source: str
    target: str
    kind: EdgeKind
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphPayload:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    query: str = ""
    view: ViewMode = "global"
    min_similarity: float = 0.72

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "view": self.view,
            "min_similarity": self.min_similarity,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }
