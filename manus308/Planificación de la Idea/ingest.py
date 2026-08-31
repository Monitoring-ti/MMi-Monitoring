#!/usr/bin/env python3
"""
MMI — Fase 1 · Orquestador de ingesta.

Flujo por documento:
  1. SHA-256 del binario -> versionado / detección de duplicados.
  2. Extraer bloques (PDF/XLSX/PPTX).
  3. Chunking adaptativo con guardas de seguridad.
  4. Embed denso (OpenAI) + disperso (BM25).
  5. Upsert en Qdrant (payload con tenant, criticidad, activos, versionado).
  6. Registrar en Postgres (documents + chunks con qdrant_point_id).

La escritura es en dos fases: primero Qdrant, luego Postgres. Si Postgres
falla, los puntos de Qdrant quedan con el document_id para reconciliación.

Uso:
    python3 ingest.py <archivo> <tenant_slug> <tipo> [version_label] [dominio]
"""
from __future__ import annotations

import os
import sys
import uuid

import requests

sys.path.insert(0, os.path.dirname(__file__))

from chunking import chunk_blocks, file_sha256
from extractors import extract
from providers import OpenAIEmbedding, SparseEncoder

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector

SUPA_URL = os.environ["NEXT_PUBLIC_SUPABASE_URL"].rstrip("/")
SUPA_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REST = f"{SUPA_URL}/rest/v1"
HEADERS = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# Mapeo extensión -> extraction_method
EXT_METHOD = {".pdf": "native", ".xlsx": "tabular", ".pptx": "slide", ".docx": "native"}


# ----------------------------------------------------------------------------
# Postgres (vía PostgREST con service_role)
# ----------------------------------------------------------------------------

def pg_get_tenant_id(slug: str) -> str:
    r = requests.get(f"{REST}/tenants", params={"slug": f"eq.{slug}", "select": "id"},
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise ValueError(f"Tenant '{slug}' no existe. Créalo primero.")
    return rows[0]["id"]


def pg_find_document(tenant_id: str, file_hash: str):
    """Busca un documento por hash (para versionado/duplicados)."""
    r = requests.get(f"{REST}/documents",
                     params={"tenant_id": f"eq.{tenant_id}",
                             "file_hash": f"eq.{file_hash}", "select": "id,is_current"},
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def pg_insert_document(doc: dict) -> str:
    r = requests.post(f"{REST}/documents", headers=HEADERS, json=doc, timeout=30)
    r.raise_for_status()
    return r.json()[0]["id"]


def pg_insert_chunks(rows: list[dict]) -> None:
    # Insertar en lotes de 500 filas (mejor práctica Postgres: 500-1000).
    for i in range(0, len(rows), 500):
        r = requests.post(f"{REST}/chunks", headers=HEADERS, json=rows[i:i + 500], timeout=120)
        r.raise_for_status()


def pg_delete_document(doc_id: str) -> None:
    """Borra un documento y sus chunks (cascade) de Postgres."""
    r = requests.delete(f"{REST}/documents", params={"id": f"eq.{doc_id}"},
                        headers=HEADERS, timeout=30)
    r.raise_for_status()


def qdrant_delete_document(client: QdrantClient, doc_id: str) -> None:
    """Borra los puntos de un documento en Qdrant por filtro de payload."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    client.delete(
        collection_name="mmi_chunks",
        points_selector=Filter(must=[FieldCondition(
            key="document_id", match=MatchValue(value=doc_id))]),
        wait=True,
    )


def reingest(path: str, tenant_slug: str, tipo: str,
             version_label: str | None = None, dominio: str | None = None) -> dict:
    """Reindexa un documento: borra la versión previa (Postgres + Qdrant) y lo
    vuelve a ingerir con el chunker actual."""
    file_hash = file_sha256(path)
    tenant_id = pg_get_tenant_id(tenant_slug)
    existing = pg_find_document(tenant_id, file_hash)
    if existing:
        doc_id = existing[0]["id"]
        client = qdrant_client()
        qdrant_delete_document(client, doc_id)
        pg_delete_document(doc_id)
    return ingest(path, tenant_slug, tipo, version_label, dominio)


# ----------------------------------------------------------------------------
# Qdrant
# ----------------------------------------------------------------------------

def qdrant_client() -> QdrantClient:
    return QdrantClient(url=os.environ["QDRANT_URL"],
                        api_key=os.environ["QDRANT_API_KEY"], timeout=60)


def qdrant_upsert(client: QdrantClient, points: list[PointStruct]) -> None:
    # upload_points gestiona batching (128) y paralelización (2 hilos).
    client.upload_points(collection_name="mmi_chunks", points=points,
                         batch_size=128, parallel=2, wait=True)


# ----------------------------------------------------------------------------
# Pipeline principal
# ----------------------------------------------------------------------------

def ingest(path: str, tenant_slug: str, tipo: str,
           version_label: str | None = None, dominio: str | None = None) -> dict:
    fname = os.path.basename(path)
    fmt = os.path.splitext(path)[1].lower()
    file_hash = file_sha256(path)
    tenant_id = pg_get_tenant_id(tenant_slug)

    # Versionado / duplicados: ¿ya existe este hash para el tenant?
    existing = pg_find_document(tenant_id, file_hash)
    if existing:
        return {"archivo": fname, "estado": "duplicado", "document_id": existing[0]["id"],
                "chunks": 0, "sha256": file_hash[:12]}

    # 1-2. Extraer y chunkear
    blocks = extract(path)
    chunks = chunk_blocks(blocks, fmt, tipo)
    if not chunks:
        return {"archivo": fname, "estado": "sin_contenido", "chunks": 0,
                "sha256": file_hash[:12]}

    # 3. Registrar el documento en Postgres (sin chunks aún)
    doc_id = pg_insert_document({
        "tenant_id": tenant_id,
        "titulo": fname,
        "tipo": tipo,
        "dominio": dominio,
        "file_hash": file_hash,
        "version_label": version_label,
        "is_current": True,
        "extraction_method": EXT_METHOD.get(fmt, "native"),
        "source_file_id": path,
    })

    # 4. Embed denso + disperso (en lotes para no exceder memoria)
    emb = OpenAIEmbedding()
    sp = SparseEncoder()
    texts = [c.content for c in chunks]

    dense_vecs: list[list[float]] = []
    BATCH = 64
    for i in range(0, len(texts), BATCH):
        dense_vecs.extend(emb.embed(texts[i:i + BATCH]))
    sparse_vecs = sp.encode(texts)

    # 5. Upsert en Qdrant
    client = qdrant_client()
    points = []
    for c, dv, (si, sv) in zip(chunks, dense_vecs, sparse_vecs):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{c.chunk_index}"))
        c.qdrant_point_id = point_id
        points.append(PointStruct(
            id=point_id,
            vector={"dense": dv, "sparse": SparseVector(indices=si, values=sv)},
            payload={
                "tenant_id": tenant_id,
                "document_id": doc_id,
                "chunk_index": c.chunk_index,
                "tipo": tipo,
                "dominio": dominio,
                "criticality_level": c.criticality_level,
                "asset_codes": c.asset_codes or [],
                "is_current": True,
                "extraction_method": EXT_METHOD.get(fmt, "native"),
                "section_path": c.section_path,
                "content": c.content[:4000],  # payload acotado
            },
        ))
    qdrant_upsert(client, points)

    # 6. Registrar chunks en Postgres con el qdrant_point_id
    rows = [{
        "tenant_id": tenant_id,
        "document_id": doc_id,
        "chunk_index": c.chunk_index,
        "content": c.content,
        "token_count": c.token_count,
        "page_start": c.page_start,
        "page_end": c.page_end,
        "section_path": c.section_path,
        "criticality_level": c.criticality_level,
        "asset_codes": c.asset_codes or [],
        "qdrant_point_id": c.qdrant_point_id,
    } for c in chunks]
    pg_insert_chunks(rows)

    return {"archivo": fname, "estado": "indexado", "document_id": doc_id,
            "chunks": len(chunks), "tokens": sum(c.token_count for c in chunks),
            "sha256": file_hash[:12]}


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit("Uso: ingest.py <archivo> <tenant_slug> <tipo> [version_label] [dominio]")
    path, tenant, tipo = sys.argv[1], sys.argv[2], sys.argv[3]
    version = sys.argv[4] if len(sys.argv) > 4 else None
    dominio = sys.argv[5] if len(sys.argv) > 5 else None
    res = ingest(path, tenant, tipo, version, dominio)
    print(res)
