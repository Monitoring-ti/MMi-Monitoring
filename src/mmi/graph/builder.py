"""Construcción del grafo desde búsqueda híbrida y expansión Qdrant."""

from __future__ import annotations

from typing import Any

from qdrant_client.models import FieldCondition, Filter, MatchValue

from mmi.graph.concepts import attach_conflict_edges, attach_concepts
from mmi.graph.models import GraphEdge, GraphNode, GraphPayload, ViewMode
from mmi.search.engine import HybridSearchEngine, SearchResult, _chunk_meta, _doc_meta, format_citation


def _doc_node_id(document_id: str) -> str:
    return f"doc:{document_id}"


def _chunk_node_id(point_id: str) -> str:
    return f"chunk:{point_id}"


def _asset_node_id(code: str) -> str:
    return f"asset:{code.upper()}"


def _edge_id(source: str, target: str, kind: str) -> str:
    return f"{kind}:{source}->{target}"


def _chunk_label(hit: SearchResult) -> str:
    title = hit.titulo or hit.document_key or "Fragmento"
    if hit.page_start is not None:
        return f"{title} p.{hit.page_start}"
    if hit.section_path:
        return f"{hit.section_path[:40]}"
    return title[:72]


def _hit_to_chunk_node(hit: SearchResult, *, score: float | None = None) -> GraphNode:
    return GraphNode(
        id=_chunk_node_id(hit.point_id),
        kind="chunk",
        label=_chunk_label(hit),
        score=score if score is not None else hit.score,
        document_id=hit.document_id,
        point_id=hit.point_id,
        tipo=hit.tipo,
        dominio=hit.dominio,
        document_key=hit.document_key,
        version_label=hit.version_label,
        citation=hit.citation,
        content_preview=(hit.content or "")[:500],
        asset_codes=list(hit.asset_codes or []),
        page_start=hit.page_start,
        page_end=hit.page_end,
    )


def _document_node_from_hit(hit: SearchResult) -> GraphNode:
    label = hit.titulo or hit.document_key or "Documento"
    if hit.version_label:
        label = f"{label} ({hit.version_label})"
    return GraphNode(
        id=_doc_node_id(hit.document_id),
        kind="document",
        label=label[:80],
        score=hit.score,
        document_id=hit.document_id,
        tipo=hit.tipo,
        dominio=hit.dominio,
        document_key=hit.document_key,
        version_label=hit.version_label,
        citation=hit.citation,
        content_preview=label,
    )


def _asset_node(code: str) -> GraphNode:
    return GraphNode(
        id=_asset_node_id(code),
        kind="asset",
        label=code.upper(),
        score=0.0,
        asset_codes=[code.upper()],
        meta={"asset_code": code.upper()},
    )


def _point_to_hit(point, *, fallback_score: float = 0.0) -> SearchResult:
    pl = point.payload or {}
    return SearchResult(
        point_id=str(point.id),
        score=float(getattr(point, "score", None) or fallback_score),
        content=pl.get("content") or "",
        document_id=pl.get("document_id") or "",
        tipo=pl.get("tipo") or "otro",
        dominio=pl.get("dominio"),
        criticality_level=pl.get("criticality_level") or "normal",
        section_path=pl.get("section_path"),
        page_start=pl.get("page_start"),
        page_end=pl.get("page_end"),
        asset_codes=pl.get("asset_codes") or [],
        chunk_index=pl.get("chunk_index"),
        version_label=pl.get("version_label"),
        document_key=pl.get("document_key"),
        version_status=pl.get("version_status"),
        is_current=bool(pl.get("is_current", True)),
    )


def _enrich_hits(hits: list[SearchResult]) -> list[SearchResult]:
    if not hits:
        return hits
    docs = _doc_meta(list({h.document_id for h in hits if h.document_id}))
    chunks = _chunk_meta([h.point_id for h in hits])
    for h in hits:
        dm = docs.get(h.document_id, {})
        cm = chunks.get(h.point_id, {})
        h.titulo = dm.get("titulo")
        h.version_label = dm.get("version_label")
        h.document_key = dm.get("document_key")
        h.page_start = cm.get("page_start") or h.page_start
        h.page_end = cm.get("page_end") or h.page_end
        h.section_path = cm.get("section_path") or h.section_path
        h.chunk_index = cm.get("chunk_index") if cm.get("chunk_index") is not None else h.chunk_index
        if cm.get("content"):
            h.content = cm["content"]
        h.citation = format_citation(
            h.titulo,
            h.version_label,
            h.tipo,
            h.page_start,
            h.page_end,
            h.section_path,
            h.chunk_index,
        )
    return hits


class GraphBuilder:
    def __init__(self, engine: HybridSearchEngine) -> None:
        self.engine = engine

    def _tenant_filter(self) -> Filter:
        return Filter(
            must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=self.engine._tenant_id)),
                FieldCondition(key="is_current", match=MatchValue(value=True)),
            ]
        )

    def search_seed(
        self,
        query: str,
        *,
        limit: int = 8,
        min_similarity: float = 0.72,
        view: ViewMode = "global",
        filters: dict[str, Any] | None = None,
    ) -> GraphPayload:
        hits = self.engine.search(query, limit=limit)
        hits = self._apply_filters(hits, filters)
        return self._build_from_hits(
            hits,
            query=query,
            min_similarity=min_similarity,
            view=view,
        )

    def expand(
        self,
        node_ids: list[str],
        *,
        limit: int = 12,
        min_similarity: float = 0.72,
        view: ViewMode = "global",
        filters: dict[str, Any] | None = None,
        existing: GraphPayload | None = None,
    ) -> GraphPayload:
        point_ids = [nid.removeprefix("chunk:") for nid in node_ids if nid.startswith("chunk:")]
        if not point_ids:
            return existing or GraphPayload(nodes=[], edges=[], min_similarity=min_similarity, view=view)

        neighbor_hits: list[SearchResult] = []
        for pid in point_ids:
            try:
                recs = self.engine.client.recommend(
                    collection_name=self.engine.collection,
                    positive=[pid],
                    limit=limit,
                    query_filter=self._tenant_filter(),
                    with_payload=True,
                )
            except Exception:  # noqa: BLE001
                continue
            for point in recs:
                score = float(point.score or 0)
                if score < min_similarity:
                    continue
                if str(point.id) in point_ids:
                    continue
                neighbor_hits.append(_point_to_hit(point, fallback_score=score))

        neighbor_hits = self._apply_filters(neighbor_hits, filters)
        seed_hits = self._fetch_hits(point_ids)
        merged: dict[str, SearchResult] = {h.point_id: h for h in seed_hits}
        for h in neighbor_hits:
            merged[h.point_id] = h
        if existing:
            for n in existing.nodes:
                if n.kind == "chunk" and n.point_id:
                    if n.point_id not in merged:
                        merged[n.point_id] = SearchResult(
                            point_id=n.point_id,
                            score=n.score,
                            content=n.content_preview,
                            document_id=n.document_id or "",
                            tipo=n.tipo or "otro",
                            dominio=n.dominio,
                            criticality_level="normal",
                            section_path=None,
                            page_start=n.page_start,
                            page_end=n.page_end,
                            asset_codes=n.asset_codes,
                            chunk_index=None,
                            version_label=n.version_label,
                            document_key=n.document_key,
                            citation=n.citation,
                        )

        return self._build_from_hits(
            list(merged.values()),
            query=existing.query if existing else "",
            min_similarity=min_similarity,
            view=view,
            include_neighbors=True,
            seed_point_ids=set(point_ids),
        )

    def get_node(self, node_id: str) -> GraphNode | None:
        if node_id.startswith("chunk:"):
            hits = self._fetch_hits([node_id.removeprefix("chunk:")])
            return _hit_to_chunk_node(hits[0]) if hits else None
        if node_id.startswith("doc:"):
            return GraphNode(
                id=node_id,
                kind="document",
                label=node_id.removeprefix("doc:")[:48],
                document_id=node_id.removeprefix("doc:"),
            )
        if node_id.startswith("asset:"):
            return _asset_node(node_id.removeprefix("asset:"))
        return None

    def hits_for_nodes(self, node_ids: list[str]) -> list[SearchResult]:
        point_ids = [nid.removeprefix("chunk:") for nid in node_ids if nid.startswith("chunk:")]
        return self._fetch_hits(point_ids)

    def filter_options(self) -> dict[str, Any]:
        return {
            "dominios": ["mantenibilidad", "confiabilidad", "seguridad", "ingenieria"],
            "tipos": ["norma", "guia", "sop", "manual_oem", "tabla", "presentacion", "plano", "otro"],
            "version_labels": ["vigente", "Rev 6", "REV02", "Rev 15"],
            "views": ["global", "documents", "concepts"],
        }

    def _fetch_hits(self, point_ids: list[str]) -> list[SearchResult]:
        if not point_ids:
            return []
        records = self.engine.client.retrieve(
            collection_name=self.engine.collection,
            ids=point_ids,
            with_payload=True,
        )
        hits = [_point_to_hit(r, fallback_score=0.5) for r in records]
        return _enrich_hits(hits)

    def _apply_filters(
        self,
        hits: list[SearchResult],
        filters: dict[str, Any] | None,
    ) -> list[SearchResult]:
        if not filters:
            return hits
        asset = (filters.get("asset") or "").strip().upper()
        dominio = (filters.get("dominio") or "").strip().lower()
        tipo = (filters.get("tipo") or "").strip().lower()
        document_key = (filters.get("document_key") or "").strip().lower()
        version = (filters.get("version_label") or filters.get("version") or "").strip().lower()
        text = (filters.get("failure") or filters.get("falla") or "").strip().lower()

        out: list[SearchResult] = []
        for h in hits:
            if asset and not any(a.upper() == asset for a in (h.asset_codes or [])):
                blob = f"{h.content} {h.titulo}".upper()
                if asset not in blob:
                    continue
            if dominio and (h.dominio or "").lower() != dominio:
                continue
            if tipo and (h.tipo or "").lower() != tipo:
                continue
            if version and version not in (h.version_label or "").lower():
                continue
            if document_key and document_key not in (h.document_key or "").lower():
                if document_key not in (h.titulo or "").lower():
                    continue
            if text:
                blob = f"{h.content} {h.titulo} {h.section_path}".lower()
                if text not in blob:
                    continue
            out.append(h)
        return out

    def _build_from_hits(
        self,
        hits: list[SearchResult],
        *,
        query: str = "",
        min_similarity: float = 0.72,
        view: ViewMode = "global",
        include_neighbors: bool = False,
        seed_point_ids: set[str] | None = None,
    ) -> GraphPayload:
        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}
        doc_keys: dict[str, list[str]] = {}
        seeds = seed_point_ids or set()

        for hit in hits:
            if hit.score < min_similarity and hit.point_id not in seeds:
                continue
            chunk = _hit_to_chunk_node(hit)
            nodes[chunk.id] = chunk

            if hit.document_id:
                doc = _document_node_from_hit(hit)
                nodes[doc.id] = doc
                edges[_edge_id(chunk.id, doc.id, "part_of")] = GraphEdge(
                    id=_edge_id(chunk.id, doc.id, "part_of"),
                    source=chunk.id,
                    target=doc.id,
                    kind="part_of",
                    weight=1.0,
                )

            for code in hit.asset_codes or []:
                asset = _asset_node(code)
                nodes[asset.id] = asset
                edges[_edge_id(chunk.id, asset.id, "mentions_asset")] = GraphEdge(
                    id=_edge_id(chunk.id, asset.id, "mentions_asset"),
                    source=chunk.id,
                    target=asset.id,
                    kind="mentions_asset",
                    weight=0.9,
                )

            if hit.document_key:
                doc_keys.setdefault(hit.document_key, []).append(chunk.id)

        if include_neighbors and len(hits) > 1:
            sorted_hits = sorted(hits, key=lambda h: h.score, reverse=True)
            for i, a in enumerate(sorted_hits):
                for b in sorted_hits[i + 1 : i + 4]:
                    if a.document_id == b.document_id:
                        continue
                    sim = min(a.score, b.score)
                    if sim < min_similarity:
                        continue
                    ca, cb = _chunk_node_id(a.point_id), _chunk_node_id(b.point_id)
                    if ca in nodes and cb in nodes:
                        eid = _edge_id(ca, cb, "similar_to")
                        edges[eid] = GraphEdge(
                            id=eid,
                            source=ca,
                            target=cb,
                            kind="similar_to",
                            weight=round(sim, 4),
                        )

        for chunk_ids in doc_keys.values():
            if len(chunk_ids) < 2:
                continue
            for i, cid in enumerate(chunk_ids):
                for other in chunk_ids[i + 1 :]:
                    eid = _edge_id(cid, other, "same_document_key")
                    edges[eid] = GraphEdge(
                        id=eid,
                        source=cid,
                        target=other,
                        kind="same_document_key",
                        weight=0.85,
                    )

        attach_concepts(hits, nodes, edges, chunk_id_for=_chunk_node_id)
        conflicts = attach_conflict_edges(hits, nodes, edges, chunk_id_for=_chunk_node_id)

        filtered_nodes, filtered_edges = self._apply_view(nodes, edges, view)
        return GraphPayload(
            nodes=list(filtered_nodes.values()),
            edges=list(filtered_edges.values()),
            query=query,
            view=view,
            min_similarity=min_similarity,
            conflicts=conflicts,
        )

    def _apply_view(
        self,
        nodes: dict[str, GraphNode],
        edges: dict[str, GraphEdge],
        view: ViewMode,
    ) -> tuple[dict[str, GraphNode], dict[str, GraphEdge]]:
        if view == "global":
            return nodes, edges
        if view == "documents":
            allowed = {nid for nid, n in nodes.items() if n.kind in {"chunk", "document"}}
        else:
            allowed = {nid for nid, n in nodes.items() if n.kind in {"asset", "concept"}}
        kept = {nid: n for nid, n in nodes.items() if nid in allowed}
        kept_edges = {
            eid: e for eid, e in edges.items() if e.source in kept and e.target in kept
        }
        return kept, kept_edges
