"""Etapas de ingesta desacopladas (B2) — funciones puras invocables por worker."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

StageName = Literal[
    "received",
    "validate",
    "extract",
    "chunk",
    "identity",
    "register",
    "embed",
    "index",
    "validate_index",
    "activate",
]

STAGE_ORDER: tuple[StageName, ...] = (
    "received",
    "validate",
    "extract",
    "chunk",
    "identity",
    "register",
    "embed",
    "index",
    "validate_index",
    "activate",
)


@dataclass
class StageContext:
    path: Path
    tenant_slug: str = "monitoring"
    tipo: str = "otro"
    document_key: str | None = None
    version_label: str | None = None
    origen: str = "ods1"
    relative_path: str = ""
    file_hash: str | None = None
    content_hash: str | None = None
    logical_key: str | None = None
    identity_decision: str | None = None
    dominio: str | None = None
    asset_tag: str = ""
    modulo: str = ""
    tenant_id: str | None = None
    activate: bool = True
    supersedes_document_id: str | None = None
    blocks: list[Any] = field(default_factory=list)
    chunks: list[Any] = field(default_factory=list)
    dense_vectors: list[list[float]] = field(default_factory=list)
    sparse_vectors: list[tuple[list[int], list[float]]] = field(default_factory=list)
    document_id: str | None = None
    catalog_id: str | None = None
    job_id: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class StageResult:
    stage: StageName
    ok: bool
    next_stage: StageName | None = None
    skip: bool = False
    reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


def next_stage(current: StageName) -> StageName | None:
    try:
        idx = STAGE_ORDER.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(STAGE_ORDER):
        return None
    return STAGE_ORDER[idx + 1]


def stage_validate(ctx: StageContext) -> StageResult:
    from mmi.catalog.assets import validate_asset_tag
    from mmi.catalog.version_detect import DocumentCandidate
    from mmi.index.chunking import file_sha256
    from mmi.index.pipeline import validate_ingest_metadata, _map_tipo
    from mmi.index.store import pg_find_document, pg_get_tenant_id, pg_schema_v2

    if not ctx.path.exists():
        return StageResult("validate", ok=False, reason=f"no existe: {ctx.path}")

    ctx.file_hash = ctx.file_hash or file_sha256(ctx.path)
    if ctx.asset_tag:
        try:
            if not validate_asset_tag(ctx.asset_tag):
                ctx.metrics.setdefault("warnings", []).append(
                    f"asset_tag '{ctx.asset_tag}' no está en catalog_assets"
                )
        except RuntimeError:
            pass
    candidate = DocumentCandidate.from_ingest(
        ctx.path,
        tenant_slug=ctx.tenant_slug,
        tipo=ctx.tipo,
        document_key=ctx.document_key,
        version_label=ctx.version_label,
        origen=ctx.origen,
        relative_path=ctx.relative_path,
        asset_tag=ctx.asset_tag,
        modulo=ctx.modulo,
    )
    ctx.logical_key = candidate.logical_key
    tipo_db = _map_tipo(ctx.tipo)
    validate_ingest_metadata(
        document_key=candidate.logical_key,
        tipo=tipo_db,
        tenant_slug=ctx.tenant_slug,
    )

    if pg_schema_v2():
        ctx.tenant_id = ctx.tenant_id or pg_get_tenant_id(ctx.tenant_slug)
        existing = pg_find_document(ctx.tenant_id, ctx.file_hash)
        if existing:
            row = existing[0]
            return StageResult(
                "validate",
                ok=True,
                skip=True,
                reason="file_hash duplicado",
                payload={
                    "estado": "duplicado",
                    "document_id": row.get("id"),
                    "document_key": row.get("document_key") or ctx.logical_key,
                },
            )

    if not ctx.dominio:
        from mmi.index.pipeline import DOMINIO_BY_TIPO

        ctx.dominio = DOMINIO_BY_TIPO.get(tipo_db, "mantenibilidad")

    return StageResult("validate", ok=True, next_stage="extract")


def stage_extract(ctx: StageContext) -> StageResult:
    from mmi.index.blocks import blocks_from_path
    from mmi.index.pipeline import _map_tipo

    tipo_db = _map_tipo(ctx.tipo)
    ctx.blocks = blocks_from_path(
        ctx.path,
        document_key=ctx.logical_key or ctx.document_key or ctx.path.stem,
        version_label=ctx.version_label or "",
        tipo=tipo_db,
    )
    if not ctx.blocks:
        return StageResult("extract", ok=False, reason="sin contenido extraíble")
    return StageResult("extract", ok=True, next_stage="chunk")


def stage_chunk(ctx: StageContext) -> StageResult:
    from mmi.index.chunking import chunk_blocks
    from mmi.index.content_hash import content_hash
    from mmi.index.pipeline import _map_tipo

    fmt = ctx.path.suffix.lower()
    tipo_db = _map_tipo(ctx.tipo)
    ctx.chunks = chunk_blocks(ctx.blocks, fmt, tipo_db)
    if not ctx.chunks:
        return StageResult("chunk", ok=False, reason="sin chunks")
    normalized = "\n\n".join(c.content for c in ctx.chunks)
    ctx.content_hash = content_hash(normalized)
    ctx.metrics["chunks"] = len(ctx.chunks)
    ctx.metrics["tokens"] = sum(c.token_count for c in ctx.chunks)
    return StageResult("chunk", ok=True, next_stage="identity")


def stage_identity(ctx: StageContext) -> StageResult:
    from mmi.catalog.version_detect import DocumentCandidate, resolve_ingest_decision
    from mmi.index.store import pg_find_document_by_key_content, pg_get_tenant_id, pg_patch_document, pg_schema_v2

    if not ctx.content_hash:
        return StageResult("identity", ok=False, reason="sin content_hash")

    candidate = DocumentCandidate.from_ingest(
        ctx.path,
        tenant_slug=ctx.tenant_slug,
        tipo=ctx.tipo,
        document_key=ctx.document_key,
        version_label=ctx.version_label,
        origen=ctx.origen,
        relative_path=ctx.relative_path,
        asset_tag=ctx.asset_tag,
        modulo=ctx.modulo,
    )
    decision = resolve_ingest_decision(
        candidate,
        content_hash_value=ctx.content_hash,
        tenant_slug=ctx.tenant_slug,
    )
    ctx.identity_decision = decision.kind
    ctx.logical_key = decision.logical_key
    ctx.metrics["identity_decision"] = decision.kind
    ctx.metrics["identity_reason"] = decision.reason
    ctx.metrics["content_hash"] = ctx.content_hash[:12]
    ctx.metrics["confidence"] = decision.confidence

    if decision.kind == "needs_review":
        return StageResult(
            "identity",
            ok=True,
            skip=True,
            reason=decision.reason,
            payload={"estado": "needs_review"},
        )

    if decision.kind == "mismo_contenido":
        existing_id = decision.existing_document_id
        if not existing_id and pg_schema_v2():
            tenant_id = ctx.tenant_id or pg_get_tenant_id(ctx.tenant_slug)
            hits = pg_find_document_by_key_content(tenant_id, decision.logical_key, ctx.content_hash)
            existing_id = hits[0]["id"] if hits else None
        if existing_id and ctx.version_label:
            pg_patch_document(existing_id, {"version_label": ctx.version_label})
        return StageResult(
            "identity",
            ok=True,
            skip=True,
            reason=decision.reason,
            payload={"estado": "mismo_contenido", "document_id": existing_id},
        )

    if decision.kind == "duplicado_fisico":
        return StageResult(
            "identity",
            ok=True,
            skip=True,
            reason=decision.reason,
            payload={"estado": "duplicado"},
        )

    ctx.supersedes_document_id = decision.supersedes_document_id
    return StageResult("identity", ok=True, next_stage="register")


def stage_register(ctx: StageContext) -> StageResult:
    from mmi.index.pipeline import _map_tipo, requests_patch_job_document
    from mmi.index.store import (
        EXT_METHOD,
        pg_get_document,
        pg_get_tenant_id,
        pg_insert_document,
        pg_insert_ingestion_job,
        pg_patch_document,
        pg_schema_v2,
        pg_upsert_catalog,
    )

    if not pg_schema_v2():
        return StageResult("register", ok=False, reason="schema v2 no disponible")

    if ctx.document_id:
        doc = pg_get_document(ctx.document_id) or {}
        ctx.catalog_id = ctx.catalog_id or doc.get("catalog_id")
        ctx.tenant_id = ctx.tenant_id or doc.get("tenant_id")
        ctx.content_hash = ctx.content_hash or doc.get("content_hash")
        return StageResult(
            "register",
            ok=True,
            next_stage="embed",
            payload={"resumed": True, "document_id": ctx.document_id},
        )

    fmt = ctx.path.suffix.lower()
    tipo_db = _map_tipo(ctx.tipo)
    fname = ctx.path.name
    tenant_id = ctx.tenant_id or pg_get_tenant_id(ctx.tenant_slug)
    ctx.tenant_id = tenant_id
    doc_key = ctx.logical_key or ctx.document_key or ctx.path.stem

    ctx.catalog_id = pg_upsert_catalog(
        tenant_id,
        doc_key,
        titulo=fname,
        tipo=tipo_db,
        dominio=ctx.dominio or "mantenibilidad",
        origen=ctx.origen,
    )

    identity_metrics = {
        "archivo": fname,
        "identity_decision": ctx.identity_decision,
        "logical_key": doc_key,
        "content_hash": (ctx.content_hash or "")[:12],
    }
    ctx.job_id = pg_insert_ingestion_job(
        {
            "tenant_id": tenant_id,
            "catalog_id": ctx.catalog_id,
            "stage": "chunk",
            "status": "running",
            "metrics": identity_metrics,
        }
    )

    ctx.document_id = pg_insert_document(
        {
            "tenant_id": tenant_id,
            "catalog_id": ctx.catalog_id,
            "document_key": doc_key,
            "titulo": fname,
            "tipo": tipo_db,
            "dominio": ctx.dominio or "mantenibilidad",
            "file_hash": ctx.file_hash,
            "content_hash": ctx.content_hash,
            "version_label": ctx.version_label,
            "is_current": False,
            "status": "processing",
            "extraction_method": EXT_METHOD.get(fmt, "native"),
            "source_file_id": str(ctx.path.resolve()),
        }
    )
    if ctx.job_id:
        requests_patch_job_document(ctx.job_id, ctx.document_id)
    pg_patch_document(ctx.document_id, {"content_hash": ctx.content_hash, "status": "processing"})
    return StageResult("register", ok=True, next_stage="embed")


def stage_embed(ctx: StageContext) -> StageResult:
    from mmi.index.embeddings import OpenAIEmbedding, SparseEncoder

    if not ctx.chunks:
        return StageResult("embed", ok=False, reason="sin chunks")
    emb = OpenAIEmbedding()
    sparse = SparseEncoder()
    texts = [c.content for c in ctx.chunks]
    dense_vecs: list[list[float]] = []
    batch = 64
    for i in range(0, len(texts), batch):
        dense_vecs.extend(emb.embed(texts[i : i + batch]))
    ctx.dense_vectors = dense_vecs
    ctx.sparse_vectors = sparse.encode(texts)
    return StageResult("embed", ok=True, next_stage="index")


def stage_index(ctx: StageContext) -> StageResult:
    import uuid

    from qdrant_client.models import PointStruct, SparseVector

    from mmi.index.pipeline import _map_tipo
    from mmi.index.store import EXT_METHOD, pg_insert_chunks, pg_patch_document, qdrant_client, qdrant_upsert

    if not ctx.chunks or not ctx.dense_vectors or not ctx.document_id or not ctx.catalog_id:
        return StageResult("index", ok=False, reason="faltan chunks, vectores o ids")

    fmt = ctx.path.suffix.lower()
    tipo_db = _map_tipo(ctx.tipo)
    doc_key = ctx.logical_key or ctx.document_key or ctx.path.stem
    client = qdrant_client()
    points: list[PointStruct] = []
    for c, dv, (si, sv) in zip(ctx.chunks, ctx.dense_vectors, ctx.sparse_vectors):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ctx.document_id}:{c.chunk_index}"))
        c.qdrant_point_id = point_id
        points.append(
            PointStruct(
                id=point_id,
                vector={"dense": dv, "sparse": SparseVector(indices=si, values=sv)},
                payload={
                    "tenant_id": ctx.tenant_id,
                    "document_id": ctx.document_id,
                    "catalog_id": ctx.catalog_id,
                    "document_key": doc_key,
                    "chunk_index": c.chunk_index,
                    "tipo": tipo_db,
                    "dominio": ctx.dominio or "mantenibilidad",
                    "criticality_level": c.criticality_level,
                    "asset_codes": c.asset_codes or [],
                    "asset_tag": ctx.asset_tag or "",
                    "modulo": ctx.modulo or "",
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
            "tenant_id": ctx.tenant_id,
            "document_id": ctx.document_id,
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
        for c in ctx.chunks
    ]
    pg_insert_chunks(rows)
    pg_patch_document(ctx.document_id, {"status": "indexed"})
    return StageResult("index", ok=True, next_stage="validate_index")


def stage_validate_index(ctx: StageContext) -> StageResult:
    from mmi.index.store import pg_count_chunks

    if not ctx.document_id or not ctx.chunks:
        return StageResult("validate_index", ok=False, reason="sin document_id o chunks")
    expected = len(ctx.chunks)
    actual = pg_count_chunks(ctx.document_id)
    if actual != expected:
        return StageResult(
            "validate_index",
            ok=False,
            reason=f"chunks esperados {expected}, en DB {actual}",
        )
    return StageResult(
        "validate_index",
        ok=True,
        next_stage="activate" if ctx.activate else None,
        payload={"chunks_validated": actual},
    )


def stage_activate(ctx: StageContext) -> StageResult:
    from mmi.index.store import pg_activate_document_version

    if not ctx.activate:
        return StageResult("activate", ok=True, skip=True, reason="activate=false")
    if not ctx.document_id or not ctx.catalog_id or not ctx.tenant_id:
        return StageResult("activate", ok=False, reason="faltan ids para activar")
    pg_activate_document_version(
        ctx.tenant_id,
        ctx.catalog_id,
        ctx.document_id,
        expected_chunks=len(ctx.chunks),
    )
    return StageResult("activate", ok=True, payload={"estado": "active"})


STAGE_PIPELINE: tuple[tuple[StageName, Any], ...] = (
    ("validate", stage_validate),
    ("extract", stage_extract),
    ("chunk", stage_chunk),
    ("identity", stage_identity),
    ("register", stage_register),
    ("embed", stage_embed),
    ("index", stage_index),
    ("validate_index", stage_validate_index),
    ("activate", stage_activate),
)


def chunks_from_pg(rows: list[dict]) -> list[Any]:
    from mmi.index.chunking import ChunkOut

    return [
        ChunkOut(
            content=row["content"],
            chunk_index=row["chunk_index"],
            token_count=row.get("token_count") or 0,
            page_start=row.get("page_start"),
            page_end=row.get("page_end"),
            section_path=row.get("section_path"),
            criticality_level=row.get("criticality_level") or "normal",
            asset_codes=row.get("asset_codes") or [],
            qdrant_point_id=row.get("qdrant_point_id"),
        )
        for row in rows
    ]


def hydrate_context_from_document(ctx: StageContext, doc: dict[str, Any]) -> None:
    from mmi.index.store import pg_load_chunks

    ctx.document_id = doc.get("id") or ctx.document_id
    ctx.catalog_id = doc.get("catalog_id") or ctx.catalog_id
    ctx.tenant_id = doc.get("tenant_id") or ctx.tenant_id
    ctx.file_hash = doc.get("file_hash") or ctx.file_hash
    ctx.content_hash = doc.get("content_hash") or ctx.content_hash
    ctx.logical_key = doc.get("document_key") or ctx.logical_key
    ctx.dominio = doc.get("dominio") or ctx.dominio
    source = doc.get("source_file_id") or ""
    if source:
        path = Path(source)
        if path.exists():
            ctx.path = path
    if ctx.document_id and not ctx.chunks:
        rows = pg_load_chunks(ctx.document_id)
        if rows:
            ctx.chunks = chunks_from_pg(rows)
            ctx.metrics["chunks"] = len(ctx.chunks)
            ctx.metrics["tokens"] = sum(c.token_count for c in ctx.chunks)


def detect_resume_stage(document_id: str, *, activate: bool = True) -> StageName:
    from mmi.index.store import pg_chunk_point_ids, pg_count_chunks, pg_get_document

    doc = pg_get_document(document_id)
    if not doc:
        raise ValueError(f"documento no encontrado: {document_id}")

    chunk_count = pg_count_chunks(document_id)
    if chunk_count == 0:
        return "extract"

    point_count = len(pg_chunk_point_ids(document_id))
    if point_count < chunk_count:
        return "embed"

    status = doc.get("status") or "failed"
    if status == "active":
        return "validate_index"
    if activate:
        return "validate_index"
    return "validate_index"


def resume_failed_document(
    doc: dict[str, Any],
    *,
    tenant_slug: str = "monitoring",
    from_stage: StageName | None = None,
    activate: bool = True,
    tipo: str = "otro",
    relative_path: str = "",
    asset_tag: str = "",
    modulo: str = "",
) -> dict[str, Any]:
    """B2.7 — reanuda ingesta de un documento fallido hidratando contexto desde PG."""
    source = doc.get("source_file_id") or ""
    path = Path(source) if source else None
    if not path or not path.exists():
        return {
            "archivo": doc.get("titulo") or doc.get("id"),
            "document_id": doc.get("id"),
            "estado": "failed",
            "reason": "archivo fuente no existe",
        }

    ctx = StageContext(
        path=path,
        tenant_slug=tenant_slug,
        tipo=tipo,
        document_key=doc.get("document_key"),
        version_label=doc.get("version_label"),
        relative_path=relative_path,
        asset_tag=asset_tag,
        modulo=modulo,
        activate=activate,
    )
    hydrate_context_from_document(ctx, doc)
    stage = from_stage or detect_resume_stage(doc["id"], activate=activate)
    return run_full_ingest(ctx, from_stage=stage)


def list_failed_for_resume(tenant_slug: str = "monitoring", *, limit: int = 50) -> list[dict[str, Any]]:
    from mmi.index.store import pg_get_tenant_id, pg_list_failed_documents

    tenant_id = pg_get_tenant_id(tenant_slug)
    return pg_list_failed_documents(tenant_id, limit=limit)


def _stage_fns_from(start: StageName | None) -> list[Any]:
    if start is None:
        return [fn for _, fn in STAGE_PIPELINE]
    names = [name for name, _ in STAGE_PIPELINE]
    try:
        idx = names.index(start)
    except ValueError:
        return [fn for _, fn in STAGE_PIPELINE]
    return [fn for _, fn in STAGE_PIPELINE[idx:]]


def run_stages(ctx: StageContext, *, from_stage: StageName | None = None) -> list[StageResult]:
    """Ejecuta etapas en orden; se detiene en error o skip."""
    results: list[StageResult] = []
    for stage_fn in _stage_fns_from(from_stage):
        res = stage_fn(ctx)
        results.append(res)
        if not res.ok or res.skip:
            break
    return results


def run_through_chunk(ctx: StageContext) -> list[StageResult]:
    """Ejecuta validate→extract→chunk (preview sin embed)."""
    results: list[StageResult] = []
    for stage_fn in (stage_validate, stage_extract, stage_chunk):
        res = stage_fn(ctx)
        results.append(res)
        if not res.ok or res.skip:
            break
    return results


def run_full_ingest(ctx: StageContext, *, from_stage: StageName | None = None) -> dict[str, Any]:
    """Pipeline completo B2 con registro en ingestion_jobs."""
    import time

    from mmi.index.ingestion_registry import append_job
    from mmi.index.pipeline import ingest_file
    from mmi.index.store import pg_finish_ingestion_job, pg_patch_document, pg_schema_v2

    t0 = time.perf_counter()
    fname = ctx.path.name

    if not pg_schema_v2():
        return ingest_file(
            ctx.path,
            tenant_slug=ctx.tenant_slug,
            tipo=ctx.tipo,
            version_label=ctx.version_label,
            document_key=ctx.document_key,
            origen=ctx.origen,
            relative_path=ctx.relative_path,
            asset_tag=ctx.asset_tag,
            modulo=ctx.modulo,
            activate=ctx.activate,
        )

    try:
        results = run_stages(ctx, from_stage=from_stage)
    except Exception as exc:
        if ctx.job_id:
            pg_finish_ingestion_job(ctx.job_id, status="failed", error=str(exc)[:500])
        if ctx.document_id:
            pg_patch_document(ctx.document_id, {"status": "failed", "error_message": str(exc)[:500]})
        raise

    last = results[-1] if results else None
    if not last:
        return {"archivo": fname, "estado": "error", "reason": "sin etapas"}

    if last.skip:
        estado = (last.payload or {}).get("estado", "skipped")
        append_job(
            {
                "archivo": fname,
                "document_key": ctx.logical_key,
                "estado": estado,
                "file_hash": ctx.file_hash,
                "document_id": (last.payload or {}).get("document_id"),
                "stage": last.stage,
                "reason": last.reason,
                "metrics": ctx.metrics,
            }
        )
        return {"archivo": fname, "estado": estado, "reason": last.reason, **(last.payload or {})}

    if not last.ok:
        if ctx.job_id:
            pg_finish_ingestion_job(ctx.job_id, status="failed", error=last.reason[:500])
        append_job(
            {
                "archivo": fname,
                "document_key": ctx.logical_key,
                "estado": "failed",
                "file_hash": ctx.file_hash,
                "document_id": ctx.document_id,
                "stage": last.stage,
                "error": last.reason,
            }
        )
        return {"archivo": fname, "estado": "failed", "stage": last.stage, "reason": last.reason}

    elapsed = int((time.perf_counter() - t0) * 1000)
    final_status = "active" if ctx.activate else "indexed"
    metrics = {
        "chunks": len(ctx.chunks),
        "tokens": sum(c.token_count for c in ctx.chunks),
        "elapsed_ms": elapsed,
        **ctx.metrics,
    }
    if ctx.supersedes_document_id:
        metrics["supersedes_document_id"] = ctx.supersedes_document_id
    if ctx.job_id:
        pg_finish_ingestion_job(ctx.job_id, status="completed", metrics=metrics)

    append_job(
        {
            "archivo": fname,
            "document_key": ctx.logical_key,
            "estado": final_status,
            "file_hash": ctx.file_hash,
            "document_id": ctx.document_id,
            "catalog_id": ctx.catalog_id,
            "chunks": len(ctx.chunks),
            "stage": "activate" if ctx.activate else "indexed",
            "metrics": metrics,
            "identity_decision": ctx.identity_decision,
        }
    )
    return {
        "archivo": fname,
        "estado": final_status,
        "document_id": ctx.document_id,
        "catalog_id": ctx.catalog_id,
        "document_key": ctx.logical_key,
        "chunks": len(ctx.chunks),
        "tokens": metrics["tokens"],
        "sha256": (ctx.file_hash or "")[:12],
        "content_hash": (ctx.content_hash or "")[:12],
        "elapsed_ms": elapsed,
        "identity_decision": ctx.identity_decision,
        "stages": [{"stage": s.stage, "ok": s.ok, "skip": s.skip, "reason": s.reason} for s in results],
    }
