#!/usr/bin/env python3
"""
MMI — Fase 0 · Creación de la colección `mmi_chunks` en Qdrant Cloud.

Diseño:
  - Vector denso  "dense"  : 1536 dims (OpenAI text-embedding-3-small), COSINE.
  - Vector disperso "sparse": BM25 vía fastembed (índice en disco para escalar).
  - Payload indexado para filtros de tenant, criticidad, activos y versionado.

Uso:
    export QDRANT_URL="https://<cluster>.cloud.qdrant.io"
    export QDRANT_API_KEY="<api_key>"
    python3 create_collection.py            # crea si no existe
    python3 create_collection.py --recreate # borra y recrea (¡destructivo!)
"""
from __future__ import annotations

import os
import sys

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    HnswConfigDiff,
    PayloadSchemaType,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

COLLECTION = "mmi_chunks"
DENSE_DIMS = 1536  # OpenAI text-embedding-3-small


def get_client() -> QdrantClient:
    url = os.environ.get("QDRANT_URL")
    api_key = os.environ.get("QDRANT_API_KEY")
    if not url or not api_key:
        sys.exit("ERROR: define QDRANT_URL y QDRANT_API_KEY en el entorno.")
    return QdrantClient(url=url, api_key=api_key, timeout=60)


def create(client: QdrantClient, recreate: bool = False) -> None:
    exists = client.collection_exists(COLLECTION)

    if exists and recreate:
        client.delete_collection(COLLECTION)
        exists = False
        print(f"· Colección '{COLLECTION}' eliminada para recreación.")

    if not exists:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config={
                "dense": VectorParams(size=DENSE_DIMS, distance=Distance.COSINE)
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=True)  # escala en disco
                )
            },
            hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
            on_disk_payload=True,
        )
        print(f"· Colección '{COLLECTION}' creada "
              f"(dense={DENSE_DIMS} COSINE + sparse BM25).")
    else:
        print(f"· Colección '{COLLECTION}' ya existe; se omite creación.")

    # Índices de payload para filtrado eficiente en la capa de acceso.
    keyword_fields = [
        "tenant_id", "document_id", "tipo", "dominio",
        "criticality_level", "extraction_method", "section_path",
        "asset_codes",
    ]
    for field in keyword_fields:
        client.create_payload_index(
            collection_name=COLLECTION,
            field_name=field,
            field_schema=PayloadSchemaType.KEYWORD,
        )
    client.create_payload_index(
        collection_name=COLLECTION,
        field_name="is_current",
        field_schema=PayloadSchemaType.BOOL,
    )
    client.create_payload_index(
        collection_name=COLLECTION,
        field_name="chunk_index",
        field_schema=PayloadSchemaType.INTEGER,
    )
    print("· Índices de payload creados:",
          ", ".join(keyword_fields + ["is_current", "chunk_index"]))


def verify(client: QdrantClient) -> None:
    info = client.get_collection(COLLECTION)
    print("\n=== Verificación ===")
    print(f"  Colección : {COLLECTION}")
    print(f"  Puntos    : {info.points_count}")
    print(f"  Estado    : {info.status}")
    vec = info.config.params.vectors
    print(f"  Dense     : {vec['dense'].size} dims, distancia {vec['dense'].distance}")


if __name__ == "__main__":
    recreate = "--recreate" in sys.argv
    c = get_client()
    create(c, recreate=recreate)
    verify(c)
    print("\nOK — colección lista.")
