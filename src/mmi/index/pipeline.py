"""Orquestador: validar → registrar → extraer → chunkear → embed → indexar → activar."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from qdrant_client.models import PointStruct, SparseVector

from mmi.index.blocks import blocks_from_path
from mmi.index.chunking import ChunkOut, chunk_blocks, file_sha256
from mmi.index.content_hash import content_hash
from mmi.index.embeddings import OpenAIEmbedding, SparseEncoder
from mmi.index.ingestion_registry import append_job
from mmi.index.store import (
    EXT_METHOD,
    pg_activate_document_version,
    pg_count_chunks,
    pg_find_document,
    pg_finish_ingestion_job,
    pg_get_tenant_id,
    pg_insert_chunks,
    pg_insert_document,
    pg_insert_ingestion_job,
    pg_patch_document,
    pg_schema_v2,
    pg_upsert_catalog,
)

DOMINIO_BY_TIPO = {
    "norma": "criticidad",
    "guia": "mantenibilidad",
    "sop": "mantenibilidad",
    "tabla": "mantenibilidad",
    "presentacion": "confiabilidad",
    "otro": "ingenieria",
}


def _map_tipo(raw: str) -> str:
    allowed = {"norma", "guia", "sop", "manual_oem", "tabla", "presentacion", "otro"}
    if raw in allowed:
        return raw
    if raw == "plano":
        return "otro"
    return "otro"


def validate_ingest_metadata(
    *,
    document_key: str | None,
    tipo: str,
    tenant_slug: str,
) -> None:
    if not tenant_slug:
        raise ValueError("tenant_slug es obligatorio")
    if not document_key or not document_key.strip():
        raise ValueError("document_key es obligatorio para ingesta versionada")
    if not tipo:
        raise ValueError("tipo documental es obligatorio")


def ingest_file(
    path: str | Path,
    tenant_slug: str = "monitoring",
    tipo: str = "otro",
    version_label: str | None = None,
    dominio: str | None = None,
    document_key: str | None = None,
    origen: str = "local",
    activate: bool = True,
) -> dict:
    t0 = time.perf_counter()
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    doc_key = (document_key or path.stem).strip()
    validate_ingest_metadata(document_key=doc_key, tipo=tipo, tenant_slug=tenant_slug)

    if not pg_schema_v2():
        return _ingest_legacy(
            path,
            tenant_slug=tenant_slug,
            tipo=tipo,
            version_label=version_label,
            dominio=dominio,
            document_key=doc_key,
        )

    fmt = path.suffix.lower()
    tipo_db = _map_tipo(tipo)
    dominio = dominio or DOMINIO_BY_TIPO.get(tipo_db, "mantenibilidad")
    fname = path.name
    file_hash = file_sha256(path)
    tenant_id = pg_get_tenant_id(tenant_slug)

    existing = pg_find_document(tenant_id, file_hash)
    if existing:
        row = existing[0]
        append_job(
            {
                "archivo": fname,
                "document_key": doc_key,
                "estado": "duplicado",
                "file_hash": file_hash,
                "document_id": row["id"],
                "stage": "skip",
            }
        )
        return {
            "archivo": fname,
            "estado": "duplicado",
            "document_id": row["id"],
            "document_key": doc_key,
            "chunks": 0,
            "sha256": file_hash[:12],
        }

    catalog_id = pg_upsert_catalog(
        tenant_id,
        doc_key,
        titulo=fname,
        tipo=tipo_db,
        dominio=dominio,
        origen=origen,
    )

    job_id = pg_insert_ingestion_job(
        {
            "tenant_id": tenant_id,
            "catalog_id": catalog_id,
            "stage": "extract",
            "status": "running",
            "metrics": {"archivo": fname},
        }
    )

    doc_id = pg_insert_document(
        {
            "tenant_id": tenant_id,
            "catalog_id": catalog_id,
            "document_key": doc_key,
            "titulo": fname,
            "tipo": tipo_db,
            "dominio": dominio,
            "file_hash": file_hash,
            "version_label": version_label,
            "is_current": False,
            "status": "processing",
            "extraction_method": EXT_METHOD.get(fmt, "native"),
            "source_file_id": str(path.resolve()),
        }
    )

    if job_id:
        requests_patch_job_document(job_id, doc_id)

    try:
        blocks = blocks_from_path(
            path,
            document_key=doc_key,
            version_label=version_label or "",
            tipo=tipo_db,
        )
        chunks = chunk_blocks(blocks, fmt, tipo_db)
        if not chunks:
            raise RuntimeError("sin contenido extraíble")

        normalized = "\n\n".join(c.content for c in chunks)
        c_hash = content_hash(normalized)
        pg_patch_document(doc_id, {"content_hash": c_hash, "status": "processing"})

        emb = OpenAIEmbedding()
        sparse = SparseEncoder()
        texts = [c.content for c in chunks]

        dense_vecs: list[list[float]] = []
        batch = 64
        for i in range(0, len(texts), batch):
            dense_vecs.extend(emb.embed(texts[i : i + batch]))
        sparse_vecs = sparse.encode(texts)

        from mmi.index.store import qdrant_client, qdrant_upsert

        client = qdrant_client()
        points: list[PointStruct] = []
        for c, dv, (si, sv) in zip(chunks, dense_vecs, sparse_vecs):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{c.chunk_index}"))
            c.qdrant_point_id = point_id
            points.append(
                PointStruct(
                    id=point_id,
                    vector={"dense": dv, "sparse": SparseVector(indices=si, values=sv)},
                    payload={
                        "tenant_id": tenant_id,
                        "document_id": doc_id,
                        "catalog_id": catalog_id,
                        "document_key": doc_key,
                        "chunk_index": c.chunk_index,
                        "tipo": tipo_db,
                        "dominio": dominio,
                        "criticality_level": c.criticality_level,
                        "asset_codes": c.asset_codes or [],
                        "is_current": False,
                        "version_status": "indexed",
                        "extraction_method": EXT_METHOD.get(fmt, "native"),
                        "section_path": c.section_path,
                        "slide_number": c.page_start if fmt == ".pptx" else None,
                        "content": c.content[:4000],
                    },
                )
            )
        qdrant_upsert(client, points)

        rows = [
            {
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
            }
            for c in chunks
        ]
        pg_insert_chunks(rows)
        pg_patch_document(doc_id, {"status": "indexed"})

        if activate:
            pg_activate_document_version(
                tenant_id,
                catalog_id,
                doc_id,
                expected_chunks=len(chunks),
            )
            final_status = "active"
        else:
            final_status = "indexed"

        elapsed = int((time.perf_counter() - t0) * 1000)
        metrics = {
            "chunks": len(chunks),
            "tokens": sum(c.token_count for c in chunks),
            "elapsed_ms": elapsed,
            "content_hash": c_hash[:12],
        }
        pg_finish_ingestion_job(job_id, status="completed", metrics=metrics)
        append_job(
            {
                "archivo": fname,
                "document_key": doc_key,
                "estado": final_status,
                "file_hash": file_hash,
                "document_id": doc_id,
                "catalog_id": catalog_id,
                "chunks": len(chunks),
                "stage": "activate" if activate else "indexed",
                "metrics": metrics,
            }
        )

        return {
            "archivo": fname,
            "estado": final_status,
            "document_id": doc_id,
            "catalog_id": catalog_id,
            "document_key": doc_key,
            "chunks": len(chunks),
            "tokens": metrics["tokens"],
            "sha256": file_hash[:12],
            "content_hash": c_hash[:12],
            "elapsed_ms": elapsed,
        }

    except Exception as exc:
        pg_patch_document(
            doc_id,
            {"status": "failed", "error_message": str(exc)[:500]},
        )
        pg_finish_ingestion_job(job_id, status="failed", error=str(exc)[:500])
        append_job(
            {
                "archivo": fname,
                "document_key": doc_key,
                "estado": "failed",
                "file_hash": file_hash,
                "document_id": doc_id,
                "error": str(exc)[:300],
                "stage": "failed",
            }
        )
        raise


def _ingest_legacy(
    path: Path,
    *,
    tenant_slug: str,
    tipo: str,
    version_label: str | None,
    dominio: str | None,
    document_key: str,
) -> dict:
    """Flujo compatible con schema 001 (sin document_catalog ni estados)."""
    fmt = path.suffix.lower()
    tipo_db = _map_tipo(tipo)
    dominio = dominio or DOMINIO_BY_TIPO.get(tipo_db, "mantenibilidad")
    fname = path.name
    file_hash = file_sha256(path)
    tenant_id = pg_get_tenant_id(tenant_slug)

    existing = pg_find_document(tenant_id, file_hash)
    if existing:
        return {
            "archivo": fname,
            "estado": "duplicado",
            "document_id": existing[0]["id"],
            "document_key": document_key,
            "chunks": 0,
            "sha256": file_hash[:12],
        }

    blocks = blocks_from_path(
        path,
        document_key=document_key,
        version_label=version_label or "",
        tipo=tipo_db,
    )
    chunks = chunk_blocks(blocks, fmt, tipo_db)
    if not chunks:
        return {"archivo": fname, "estado": "sin_contenido", "chunks": 0, "sha256": file_hash[:12]}

    doc_id = pg_insert_document(
        {
            "tenant_id": tenant_id,
            "titulo": fname,
            "tipo": tipo_db,
            "dominio": dominio,
            "file_hash": file_hash,
            "version_label": version_label,
            "is_current": True,
            "extraction_method": EXT_METHOD.get(fmt, "native"),
            "source_file_id": str(path.resolve()),
        }
    )

    emb = OpenAIEmbedding()
    sparse = SparseEncoder()
    texts = [c.content for c in chunks]
    dense_vecs: list[list[float]] = []
    for i in range(0, len(texts), 64):
        dense_vecs.extend(emb.embed(texts[i : i + 64]))
    sparse_vecs = sparse.encode(texts)

    from mmi.index.store import qdrant_client, qdrant_upsert

    client = qdrant_client()
    points: list[PointStruct] = []
    for c, dv, (si, sv) in zip(chunks, dense_vecs, sparse_vecs):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{c.chunk_index}"))
        c.qdrant_point_id = point_id
        points.append(
            PointStruct(
                id=point_id,
                vector={"dense": dv, "sparse": SparseVector(indices=si, values=sv)},
                payload={
                    "tenant_id": tenant_id,
                    "document_id": doc_id,
                    "document_key": document_key,
                    "chunk_index": c.chunk_index,
                    "tipo": tipo_db,
                    "dominio": dominio,
                    "criticality_level": c.criticality_level,
                    "asset_codes": c.asset_codes or [],
                    "is_current": True,
                    "version_status": "active",
                    "extraction_method": EXT_METHOD.get(fmt, "native"),
                    "section_path": c.section_path,
                    "content": c.content[:4000],
                },
            )
        )
    qdrant_upsert(client, points)

    rows = [
        {
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
        }
        for c in chunks
    ]
    pg_insert_chunks(rows)
    append_job(
        {
            "archivo": fname,
            "document_key": document_key,
            "estado": "indexado",
            "file_hash": file_hash,
            "document_id": doc_id,
            "chunks": len(chunks),
            "stage": "legacy",
        }
    )
    return {
        "archivo": fname,
        "estado": "indexado",
        "document_id": doc_id,
        "document_key": document_key,
        "chunks": len(chunks),
        "tokens": sum(c.token_count for c in chunks),
        "sha256": file_hash[:12],
        "modo": "legacy",
    }


def requests_patch_job_document(job_id: str, document_id: str) -> None:
    if not job_id:
        return
    import requests

    from mmi.index.store import pg_headers, pg_rest

    r = requests.patch(
        f"{pg_rest()}/ingestion_jobs",
        params={"id": f"eq.{job_id}"},
        headers=pg_headers(),
        json={"document_id": document_id},
        timeout=30,
    )
    if r.status_code != 404:
        r.raise_for_status()
