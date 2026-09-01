"""Persistencia Postgres (Supabase) + Qdrant."""

from __future__ import annotations

import os
from typing import Any

import requests
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct, SparseVector

EXT_METHOD = {
    ".pdf": "native",
    ".xlsx": "tabular",
    ".xls": "tabular",
    ".pptx": "slide",
    # DB check: native|ocr|tabular|slide (001_schema.sql)
    ".docx": "native",
    ".doc": "native",
}

VERSION_STATUSES = ("received", "processing", "indexed", "active", "failed", "superseded")


def _supabase_env() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("Define SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en .env")
    return url, key


def pg_headers() -> dict[str, str]:
    _, key = _supabase_env()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def pg_rest() -> str:
    url, _ = _supabase_env()
    return f"{url}/rest/v1"


def pg_schema_v2() -> bool:
    """True si existe tabla document_catalog (migración 002 aplicada)."""
    r = requests.get(
        f"{pg_rest()}/document_catalog",
        params={"select": "id", "limit": "1"},
        headers=pg_headers(),
        timeout=15,
    )
    return r.status_code == 200


def pg_get_tenant_id(slug: str) -> str:
    r = requests.get(
        f"{pg_rest()}/tenants",
        params={"slug": f"eq.{slug}", "select": "id"},
        headers=pg_headers(),
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise ValueError(f"Tenant '{slug}' no existe en Supabase.")
    return rows[0]["id"]


def pg_find_document_by_key_content(
    tenant_id: str,
    document_key: str,
    content_hash: str,
) -> list[dict]:
    r = requests.get(
        f"{pg_rest()}/documents",
        params={
            "tenant_id": f"eq.{tenant_id}",
            "document_key": f"eq.{document_key}",
            "content_hash": f"eq.{content_hash}",
            "select": "id,is_current,status,catalog_id,document_key,version_label",
        },
        headers=pg_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def pg_find_document(tenant_id: str, file_hash: str) -> list[dict]:
    r = requests.get(
        f"{pg_rest()}/documents",
        params={
            "tenant_id": f"eq.{tenant_id}",
            "file_hash": f"eq.{file_hash}",
            "select": "id,is_current,status,catalog_id,document_key",
        },
        headers=pg_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def pg_find_catalog(tenant_id: str, document_key: str) -> dict | None:
    r = requests.get(
        f"{pg_rest()}/document_catalog",
        params={
            "tenant_id": f"eq.{tenant_id}",
            "document_key": f"eq.{document_key}",
            "select": "id,document_key,titulo,tipo,dominio",
        },
        headers=pg_headers(),
        timeout=30,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def pg_upsert_catalog(
    tenant_id: str,
    document_key: str,
    titulo: str,
    tipo: str,
    dominio: str | None,
    origen: str = "local",
) -> str:
    existing = pg_find_catalog(tenant_id, document_key)
    if existing:
        return existing["id"]
    r = requests.post(
        f"{pg_rest()}/document_catalog",
        headers=pg_headers(),
        json={
            "tenant_id": tenant_id,
            "document_key": document_key,
            "titulo": titulo,
            "tipo": tipo,
            "dominio": dominio,
            "origen": origen,
        },
        timeout=30,
    )
    if r.status_code in {400, 409} and "document_catalog" in (r.text or ""):
        existing = pg_find_catalog(tenant_id, document_key)
        if existing:
            return existing["id"]
    r.raise_for_status()
    return r.json()[0]["id"]


def pg_insert_document(doc: dict) -> str:
    r = requests.post(f"{pg_rest()}/documents", headers=pg_headers(), json=doc, timeout=30)
    r.raise_for_status()
    return r.json()[0]["id"]


def pg_patch_document(document_id: str, fields: dict) -> None:
    r = requests.patch(
        f"{pg_rest()}/documents",
        params={"id": f"eq.{document_id}"},
        headers=pg_headers(),
        json=fields,
        timeout=30,
    )
    r.raise_for_status()


def pg_documents_for_catalog(catalog_id: str) -> list[dict]:
    r = requests.get(
        f"{pg_rest()}/documents",
        params={
            "catalog_id": f"eq.{catalog_id}",
            "select": "id,status,is_current,file_hash,version_label",
        },
        headers=pg_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def pg_get_document(document_id: str) -> dict | None:
    r = requests.get(
        f"{pg_rest()}/documents",
        params={"id": f"eq.{document_id}", "select": "*"},
        headers=pg_headers(),
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def pg_load_chunks(document_id: str) -> list[dict]:
    r = requests.get(
        f"{pg_rest()}/chunks",
        params={
            "document_id": f"eq.{document_id}",
            "select": (
                "chunk_index,content,token_count,page_start,page_end,"
                "section_path,criticality_level,asset_codes,qdrant_point_id"
            ),
            "order": "chunk_index",
        },
        headers=pg_headers(),
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def pg_list_failed_documents(tenant_id: str, *, limit: int = 50) -> list[dict]:
    r = requests.get(
        f"{pg_rest()}/documents",
        params={
            "tenant_id": f"eq.{tenant_id}",
            "status": "eq.failed",
            "select": (
                "id,titulo,document_key,status,file_hash,catalog_id,tenant_id,"
                "source_file_id,content_hash,version_label,tipo,dominio"
            ),
            "limit": str(limit),
            "order": "titulo",
        },
        headers=pg_headers(),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def pg_count_chunks(document_id: str) -> int:
    r = requests.get(
        f"{pg_rest()}/chunks",
        params={"document_id": f"eq.{document_id}", "select": "id"},
        headers={**pg_headers(), "Prefer": "count=exact"},
        timeout=60,
    )
    r.raise_for_status()
    cr = r.headers.get("content-range", "")
    if "/" in cr:
        total = cr.split("/")[-1]
        if total.isdigit():
            return int(total)
    return len(r.json())


def pg_chunk_point_ids(document_id: str) -> list[str]:
    r = requests.get(
        f"{pg_rest()}/chunks",
        params={"document_id": f"eq.{document_id}", "select": "qdrant_point_id"},
        headers=pg_headers(),
        timeout=120,
    )
    r.raise_for_status()
    return [c["qdrant_point_id"] for c in r.json() if c.get("qdrant_point_id")]


def pg_insert_chunks(rows: list[dict]) -> None:
    for i in range(0, len(rows), 500):
        r = requests.post(
            f"{pg_rest()}/chunks",
            headers=pg_headers(),
            json=rows[i : i + 500],
            timeout=120,
        )
        r.raise_for_status()


def pg_insert_ingestion_job(job: dict) -> str:
    r = requests.post(f"{pg_rest()}/ingestion_jobs", headers=pg_headers(), json=job, timeout=30)
    if r.status_code == 404:
        return ""
    r.raise_for_status()
    return r.json()[0]["id"]


def pg_finish_ingestion_job(job_id: str, *, status: str, metrics: dict | None = None, error: str | None = None) -> None:
    if not job_id:
        return
    from datetime import datetime, timezone

    payload: dict[str, Any] = {
        "status": status,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    if metrics:
        payload["metrics"] = metrics
    if error:
        payload["error_message"] = error
    r = requests.patch(
        f"{pg_rest()}/ingestion_jobs",
        params={"id": f"eq.{job_id}"},
        headers=pg_headers(),
        json=payload,
        timeout=30,
    )
    if r.status_code != 404:
        r.raise_for_status()


def pg_activate_document_version(
    tenant_id: str,
    catalog_id: str,
    document_id: str,
    *,
    expected_chunks: int,
) -> None:
    actual = pg_count_chunks(document_id)
    if actual != expected_chunks:
        raise RuntimeError(f"Validación chunks: esperados {expected_chunks}, en DB {actual}")

    point_ids = pg_chunk_point_ids(document_id)
    if len(point_ids) != expected_chunks:
        raise RuntimeError(f"Validación Qdrant ids: esperados {expected_chunks}, puntos {len(point_ids)}")

    for prev in pg_documents_for_catalog(catalog_id):
        if prev["id"] == document_id:
            continue
        if prev.get("is_current") or prev.get("status") == "active":
            pg_patch_document(
                prev["id"],
                {"is_current": False, "status": "superseded"},
            )
            qdrant_set_document_current(tenant_id, prev["id"], is_current=False, version_status="superseded")

    from datetime import datetime, timezone

    pg_patch_document(
        document_id,
        {
            "is_current": True,
            "status": "active",
            "activated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    qdrant_set_document_current(tenant_id, document_id, is_current=True, version_status="active")


def qdrant_client() -> QdrantClient:
    url = os.environ.get("QDRANT_URL")
    key = os.environ.get("QDRANT_API_KEY")
    if not url or not key:
        raise RuntimeError("Define QDRANT_URL y QDRANT_API_KEY en .env")
    return QdrantClient(url=url, api_key=key, timeout=120)


def qdrant_collection() -> str:
    return os.environ.get("QDRANT_COLLECTION", "mmi_chunks")


def qdrant_upsert(client: QdrantClient, points: list[PointStruct]) -> None:
    client.upload_points(
        collection_name=qdrant_collection(),
        points=points,
        batch_size=64,
        parallel=1,
        wait=True,
    )


def qdrant_set_document_current(
    tenant_id: str,
    document_id: str,
    *,
    is_current: bool,
    version_status: str,
) -> None:
    client = qdrant_client()
    client.set_payload(
        collection_name=qdrant_collection(),
        payload={"is_current": is_current, "version_status": version_status},
        points=Filter(
            must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
            ]
        ),
        wait=True,
    )


def qdrant_delete_document_points(tenant_id: str, document_id: str) -> int:
    client = qdrant_client()
    result = client.delete(
        collection_name=qdrant_collection(),
        points_selector=Filter(
            must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
            ]
        ),
        wait=True,
    )
    return getattr(result, "operation_id", 0) or 0


def pg_delete_chunks(document_id: str) -> None:
    r = requests.delete(
        f"{pg_rest()}/chunks",
        params={"document_id": f"eq.{document_id}"},
        headers=pg_headers(),
        timeout=120,
    )
    r.raise_for_status()


def pg_delete_document(document_id: str) -> None:
    r = requests.delete(
        f"{pg_rest()}/documents",
        params={"id": f"eq.{document_id}"},
        headers=pg_headers(),
        timeout=30,
    )
    r.raise_for_status()


def pg_list_documents(tenant_id: str, *, select: str = "id,titulo,file_hash,document_key,version_label,status,is_current") -> list[dict]:
    r = requests.get(
        f"{pg_rest()}/documents",
        params={"tenant_id": f"eq.{tenant_id}", "select": select},
        headers=pg_headers(),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()
