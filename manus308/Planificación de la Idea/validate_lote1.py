#!/usr/bin/env python3
"""
MMI — Fase 1 · Validación del lote 1.

  A. Versionado: verifica que Rev 5 y Rev 6 de la guía coexisten como dos
     documentos con distinto hash, y que la búsqueda filtra por is_current.
  B. Búsqueda híbrida (dense + sparse con RRF) sobre datos reales, con filtro
     de tenant, para consultas representativas del dominio.
"""
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from providers import OpenAIEmbedding, SparseEncoder

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Prefetch, FusionQuery, SparseVector

SUPA_URL = os.environ["NEXT_PUBLIC_SUPABASE_URL"].rstrip("/")
SUPA_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REST = f"{SUPA_URL}/rest/v1"
HEADERS = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"}

TENANT = "monitoring"


def pg(path, params):
    r = requests.get(f"{REST}{path}", params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    print("=" * 60)
    print("A. VERSIONADO — par Rev 5 / Rev 6 de la guía")
    print("=" * 60)
    docs = pg("/documents", {"titulo": "like.*GUIGS-00001*",
                             "select": "titulo,version_label,file_hash,is_current"})
    for d in docs:
        vl = d['version_label'] or '(sin rev)'
        print(f"  {vl:10} | current={d['is_current']} | "
              f"hash={d['file_hash'][:12]}… | {d['titulo'][:45]}")
    hashes = {d["file_hash"] for d in docs}
    print(f"\n  Documentos: {len(docs)} | hashes distintos: {len(hashes)} "
          f"-> {'OK (versionado)' if len(hashes) == len(docs) else 'REVISAR'}")

    print()
    print("=" * 60)
    print("B. BÚSQUEDA HÍBRIDA (dense + sparse, RRF) sobre datos reales")
    print("=" * 60)

    tenant_id = pg("/tenants", {"slug": f"eq.{TENANT}", "select": "id"})[0]["id"]
    client = QdrantClient(url=os.environ["QDRANT_URL"],
                          api_key=os.environ["QDRANT_API_KEY"], timeout=60)
    emb = OpenAIEmbedding()
    sp = SparseEncoder()

    consultas = [
        "¿Qué es la mantenibilidad y cómo se evalúa en un proyecto?",
        "modos de falla y criticidad FMECA",
        "advertencia seguridad bloqueo antes de operar equipo",
    ]

    for q in consultas:
        qd = emb.embed([q])[0]
        qs = sp.encode([q])[0]
        res = client.query_points(
            collection_name="mmi_chunks",
            prefetch=[
                Prefetch(query=qd, using="dense", limit=10),
                Prefetch(query=SparseVector(indices=qs[0], values=qs[1]),
                         using="sparse", limit=10),
            ],
            query=FusionQuery(fusion="rrf"),
            limit=3,
            query_filter=Filter(must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
                FieldCondition(key="is_current", match=MatchValue(value=True)),
            ]),
        )
        print(f"\n  Q: {q}")
        for p in res.points:
            pl = p.payload
            print(f"    [{pl['tipo']:12}|{pl['criticality_level']:9}] "
                  f"score={p.score:.3f}  {pl['content'][:70]}…")


if __name__ == "__main__":
    main()
