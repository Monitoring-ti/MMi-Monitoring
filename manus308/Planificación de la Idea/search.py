#!/usr/bin/env python3
"""
MMI — Fase 3 · Motor de búsqueda híbrida afinado.

Pipeline de consulta:
  1. Retrieval híbrido en Qdrant: prefetch denso (OpenAI) + disperso (BM25),
     fusión RRF, filtro por tenant + is_current.
  2. Boost por criticidad: los chunks 'seguridad' reciben un factor de
     ponderación cuando la consulta es de índole operativa/seguridad.
  3. Reranking: reordenamiento por score ajustado (RRF + boost + prioridad de
     versión vigente), con deduplicación por documento/sección.

Devuelve resultados enriquecidos con metadatos para la capa de evidencia.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import requests

from providers import OpenAIEmbedding, SparseEncoder

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter, FieldCondition, MatchValue, Prefetch, FusionQuery, SparseVector,
)

SUPA_URL = os.environ["NEXT_PUBLIC_SUPABASE_URL"].rstrip("/")
SUPA_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REST = f"{SUPA_URL}/rest/v1"
HEADERS = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"}

COLLECTION = "mmi_chunks"

# Consultas de índole operativa/seguridad: activan el boost de criticidad
_SAFETY_QUERY_RE = re.compile(
    r"\b(seguridad|advertencia|precauci|peligro|bloqueo|loto|riesgo|"
    r"antes de operar|procedimiento|paso a paso|cómo operar|safety|hazard)\b",
    re.IGNORECASE,
)

# Factor de boost para chunks de seguridad en consultas de seguridad
SAFETY_BOOST = 1.5
# Factor leve para priorizar la versión vigente (is_current ya filtra, pero
# refuerza el orden entre documentos del mismo tema)
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
    asset_codes: list[str] = field(default_factory=list)
    version_label: str | None = None
    titulo: str | None = None


def _tenant_id(slug: str) -> str:
    r = requests.get(f"{REST}/tenants", params={"slug": f"eq.{slug}", "select": "id"},
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise ValueError(f"Tenant '{slug}' no existe")
    return rows[0]["id"]


def _doc_meta(doc_ids: list[str]) -> dict[str, dict]:
    """Trae título y version_label de los documentos para enriquecer."""
    if not doc_ids:
        return {}
    r = requests.get(f"{REST}/documents",
                     params={"id": f"in.({','.join(doc_ids)})",
                             "select": "id,titulo,version_label"},
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    return {d["id"]: d for d in r.json()}


class HybridSearchEngine:
    """Motor de búsqueda híbrida con boost por criticidad y reranking."""

    def __init__(self, tenant_slug: str = "monitoring"):
        self.tenant_slug = tenant_slug
        self._tenant_id = _tenant_id(tenant_slug)
        self.client = QdrantClient(url=os.environ["QDRANT_URL"],
                                   api_key=os.environ["QDRANT_API_KEY"], timeout=60)
        self.emb = OpenAIEmbedding()
        self.sp = SparseEncoder()

    def _retrieve(self, query: str, limit: int, prefetch_limit: int) -> list:
        """Retrieval híbrido: dense + sparse con fusión RRF y filtro tenant."""
        qd = self.emb.embed([query])[0]
        qs = self.sp.encode([query])[0]
        res = self.client.query_points(
            collection_name=COLLECTION,
            prefetch=[
                Prefetch(query=qd, using="dense", limit=prefetch_limit),
                Prefetch(query=SparseVector(indices=qs[0], values=qs[1]),
                         using="sparse", limit=prefetch_limit),
            ],
            query=FusionQuery(fusion="rrf"),
            limit=limit,
            query_filter=Filter(must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=self._tenant_id)),
                FieldCondition(key="is_current", match=MatchValue(value=True)),
            ]),
            with_payload=True,
        )
        return res.points

    def _rerank(self, points: list, query: str, boost_safety: bool) -> list[SearchResult]:
        """Reordena por score ajustado: RRF + boost de seguridad + prioridad de
        versión vigente. Deduplica por (document_id, section_path)."""
        is_safety_query = bool(_SAFETY_QUERY_RE.search(query))
        results: list[SearchResult] = []
        seen: set[tuple] = set()

        for p in points:
            pl = p.payload or {}
            score = float(p.score)
            crit = pl.get("criticality_level", "normal")
            # Boost de seguridad solo si la consulta es de seguridad
            if boost_safety and is_safety_query and crit == "seguridad":
                score *= SAFETY_BOOST
            # Prioridad leve a la versión vigente
            if pl.get("is_current"):
                score *= CURRENT_BOOST

            key = (pl.get("document_id"), pl.get("section_path"))
            if key in seen:
                continue
            seen.add(key)

            results.append(SearchResult(
                point_id=str(p.id), score=score,
                content=pl.get("content", ""),
                document_id=pl.get("document_id", ""),
                tipo=pl.get("tipo", "otro"),
                dominio=pl.get("dominio"),
                criticality_level=crit,
                section_path=pl.get("section_path"),
                page_start=pl.get("page_start"),
                page_end=pl.get("page_end"),
                asset_codes=pl.get("asset_codes") or [],
            ))

        # Reordenar por score ajustado descendente
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def search(self, query: str, limit: int = 5, prefetch_limit: int = 20,
               boost_safety: bool = True, enrich: bool = True) -> list[SearchResult]:
        """Búsqueda híbrida afinada. Devuelve resultados rerankeados."""
        points = self._retrieve(query, limit=prefetch_limit, prefetch_limit=prefetch_limit)
        results = self._rerank(points, query, boost_safety)[:limit]

        if enrich and results:
            meta = _doc_meta(list({r.document_id for r in results}))
            for r in results:
                m = meta.get(r.document_id, {})
                r.titulo = m.get("titulo")
                r.version_label = m.get("version_label")
        return results


# ----------------------------------------------------------------------------
# CLI de prueba
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "¿Qué es el FMECA?"
    engine = HybridSearchEngine()
    print(f"Consulta: {q}\n")
    for i, r in enumerate(engine.search(q, limit=5), 1):
        sec = f" | {r.section_path[:40]}" if r.section_path else ""
        ver = f" | {r.version_label}" if r.version_label else ""
        print(f"{i}. [{r.tipo:12}|{r.criticality_level:9}] score={r.score:.3f}{sec}{ver}")
        print(f"   {r.content[:90]}…\n")
