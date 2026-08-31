"""Motor de búsqueda híbrida (dense + BM25 / RRF)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import requests
from qdrant_client.models import (
    FieldCondition,
    Filter,
    FusionQuery,
    MatchValue,
    Prefetch,
    SparseVector,
)

from mmi.index.embeddings import OpenAIEmbedding, SparseEncoder
from mmi.index.store import pg_get_tenant_id, pg_headers, pg_rest, qdrant_client, qdrant_collection

_SAFETY_QUERY_RE = re.compile(
    r"\b(seguridad|advertencia|precauci|peligro|bloqueo|loto|riesgo|"
    r"antes de operar|procedimiento|paso a paso|cómo operar|safety|hazard)\b",
    re.IGNORECASE,
)
SAFETY_BOOST = 1.5
CURRENT_BOOST = 1.1


@dataclass
class SearchResult:
    point_id: str
    score: float
    content: str
    document_id: str
    tipo: str
    dominio: str | None
    criticality_level: str
    section_path: str | None
    page_start: int | None
    page_end: int | None
    asset_codes: list[str]
    chunk_index: int | None
    version_label: str | None = None
    titulo: str | None = None
    citation: str | None = None


def _doc_meta(doc_ids: list[str]) -> dict[str, dict]:
    if not doc_ids:
        return {}
    r = requests.get(
        f"{pg_rest()}/documents",
        params={"id": f"in.({','.join(doc_ids)})", "select": "id,titulo,version_label,tipo"},
        headers=pg_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return {d["id"]: d for d in r.json()}


def _chunk_meta(point_ids: list[str]) -> dict[str, dict]:
    if not point_ids:
        return {}
    r = requests.get(
        f"{pg_rest()}/chunks",
        params={
            "qdrant_point_id": f"in.({','.join(point_ids)})",
            "select": "qdrant_point_id,page_start,page_end,content,chunk_index,section_path",
        },
        headers=pg_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return {c["qdrant_point_id"]: c for c in r.json()}


def format_citation(
    titulo: str | None,
    version_label: str | None,
    tipo: str,
    page_start: int | None,
    page_end: int | None,
    section_path: str | None,
    chunk_index: int | None,
) -> str:
    doc = titulo or "Documento"
    if version_label:
        doc += f" ({version_label})"
    if page_start is not None:
        if page_end and page_end != page_start:
            return f"{doc} — págs. {page_start}–{page_end}"
        return f"{doc} — pág. {page_start}"
    if section_path and tipo == "tabla":
        return f"{doc} — hoja/fila: {section_path}"
    if section_path:
        return f"{doc} — {section_path}"
    if chunk_index is not None:
        return f"{doc} — fragmento #{chunk_index + 1}"
    return doc


class HybridSearchEngine:
    def __init__(self, tenant_slug: str = "monitoring") -> None:
        self.tenant_slug = tenant_slug
        self._tenant_id = pg_get_tenant_id(tenant_slug)
        self.client = qdrant_client()
        self.emb = OpenAIEmbedding()
        self.sp = SparseEncoder()
        self.collection = qdrant_collection()

    def _retrieve(self, query: str, limit: int, prefetch_limit: int):
        qd = self.emb.embed([query])[0]
        qs = self.sp.encode([query])[0]
        filt = Filter(
            must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=self._tenant_id)),
                FieldCondition(key="is_current", match=MatchValue(value=True)),
            ]
        )
        if qs[0]:
            res = self.client.query_points(
                collection_name=self.collection,
                prefetch=[
                    Prefetch(query=qd, using="dense", limit=prefetch_limit),
                    Prefetch(
                        query=SparseVector(indices=qs[0], values=qs[1]),
                        using="sparse",
                        limit=prefetch_limit,
                    ),
                ],
                query=FusionQuery(fusion="rrf"),
                limit=limit,
                query_filter=filt,
                with_payload=True,
            )
        else:
            res = self.client.query_points(
                collection_name=self.collection,
                query=qd,
                using="dense",
                limit=limit,
                query_filter=filt,
                with_payload=True,
            )
        return res.points

    def _rerank(self, points: list, query: str, boost_safety: bool) -> list[SearchResult]:
        is_safety_query = bool(_SAFETY_QUERY_RE.search(query))
        results: list[SearchResult] = []
        seen: set[tuple] = set()

        for p in points:
            pl = p.payload or {}
            version_status = pl.get("version_status")
            if version_status and version_status not in {"active"}:
                continue
            if not pl.get("is_current", True):
                continue
            score = float(p.score)
            crit = pl.get("criticality_level", "normal")
            if boost_safety and is_safety_query and crit == "seguridad":
                score *= SAFETY_BOOST
            if pl.get("is_current"):
                score *= CURRENT_BOOST

            key = (pl.get("document_id"), pl.get("section_path"))
            if key in seen:
                continue
            seen.add(key)

            results.append(
                SearchResult(
                    point_id=str(p.id),
                    score=score,
                    content=pl.get("content", ""),
                    document_id=pl.get("document_id", ""),
                    tipo=pl.get("tipo", "otro"),
                    dominio=pl.get("dominio"),
                    criticality_level=crit,
                    section_path=pl.get("section_path"),
                    page_start=pl.get("page_start"),
                    page_end=pl.get("page_end"),
                    asset_codes=pl.get("asset_codes") or [],
                    chunk_index=pl.get("chunk_index"),
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def search(
        self,
        query: str,
        limit: int = 5,
        prefetch_limit: int = 20,
        boost_safety: bool = True,
        enrich: bool = True,
    ) -> list[SearchResult]:
        points = self._retrieve(query, limit=prefetch_limit, prefetch_limit=prefetch_limit)
        results = self._rerank(points, query, boost_safety)[:limit]

        if enrich and results:
            docs = _doc_meta(list({r.document_id for r in results}))
            chunks = _chunk_meta([r.point_id for r in results])
            for r in results:
                dm = docs.get(r.document_id, {})
                cm = chunks.get(r.point_id, {})
                r.titulo = dm.get("titulo")
                r.version_label = dm.get("version_label")
                r.page_start = cm.get("page_start") or r.page_start
                r.page_end = cm.get("page_end") or r.page_end
                r.section_path = cm.get("section_path") or r.section_path
                r.chunk_index = cm.get("chunk_index") if cm.get("chunk_index") is not None else r.chunk_index
                if cm.get("content") and len(cm["content"]) > len(r.content):
                    r.content = cm["content"]
                r.citation = format_citation(
                    r.titulo,
                    r.version_label,
                    r.tipo,
                    r.page_start,
                    r.page_end,
                    r.section_path,
                    r.chunk_index,
                )
        return results
