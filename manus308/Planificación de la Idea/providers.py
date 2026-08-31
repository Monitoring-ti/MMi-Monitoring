#!/usr/bin/env python3
"""
MMI — Fase 0 · Esqueleto del pipeline de ingesta.

Define las interfaces parametrizables y los providers concretos:
  - EmbeddingProvider : OpenAI (por defecto) y Mistral (contingencia).
  - OcrProvider       : Stub (por defecto, marca extraction_method='ocr' sin
                        llamar a ningún API) + hueco para Azure/Google/AWS.
  - SparseEncoder     : BM25 vía fastembed para el vector disperso de Qdrant.

El pipeline orquesta: extraer → chunk → embed → upsert Qdrant → registrar en
Postgres. La escritura es en dos fases con reconciliación para evitar
divergencia Postgres↔Qdrant.
"""
from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

# ----------------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------------

EMBEDDING_PROVIDER = os.environ.get("MMI_EMBEDDING_PROVIDER", "openai")  # openai|mistral
OCR_PROVIDER = os.environ.get("MMI_OCR_PROVIDER", "stub")                # stub|azure|google|aws
OPENAI_EMBED_MODEL = os.environ.get("MMI_OPENAI_EMBED_MODEL", "text-embedding-3-small")
MISTRAL_EMBED_MODEL = os.environ.get("MMI_MISTRAL_EMBED_MODEL", "mistral-embed")
DENSE_DIMS = 1536


# ----------------------------------------------------------------------------
# Modelos de datos del pipeline
# ----------------------------------------------------------------------------

@dataclass
class Chunk:
    """Unidad de texto lista para indexar."""
    document_id: str
    tenant_id: str
    chunk_index: int
    content: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section_path: Optional[str] = None
    criticality_level: str = "normal"      # baja|normal|alta|seguridad
    asset_codes: list[str] = field(default_factory=list)
    tipo: Optional[str] = None
    dominio: Optional[str] = None
    extraction_method: str = "native"
    is_current: bool = True
    # Salidas
    dense_vector: Optional[list[float]] = None
    sparse_indices: Optional[list[int]] = None
    sparse_values: Optional[list[float]] = None
    qdrant_point_id: Optional[str] = None

    @property
    def point_id(self) -> str:
        """ID determinista del punto Qdrant (UUID a partir de doc+index)."""
        raw = f"{self.document_id}:{self.chunk_index}".encode()
        return hashlib.sha256(raw).hexdigest()[:32]


# ----------------------------------------------------------------------------
# EmbeddingProvider (denso)
# ----------------------------------------------------------------------------

class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Devuelve un vector denso por texto."""
        ...

    @property
    @abstractmethod
    def dims(self) -> int: ...


class OpenAIEmbedding(EmbeddingProvider):
    def __init__(self, model: str = OPENAI_EMBED_MODEL):
        from openai import OpenAI
        # La key sk-proj es de OpenAI real; forzamos base_url para no usar el
        # proxy del sandbox (OPENAI_BASE_URL apunta a un proxy sin /embeddings).
        self.client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url="https://api.openai.com/v1",
        )
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]

    @property
    def dims(self) -> int:
        return DENSE_DIMS


class MistralEmbedding(EmbeddingProvider):
    """Provider de contingencia; conmutable por MMI_EMBEDDING_PROVIDER=mistral."""
    def __init__(self, model: str = MISTRAL_EMBED_MODEL):
        from mistralai import Mistral
        self.client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.embeddings.create(model=self.model, inputs=texts)
        return [d.embedding for d in resp.data]

    @property
    def dims(self) -> int:
        return 1024  # mistral-embed


def get_embedding_provider() -> EmbeddingProvider:
    if EMBEDDING_PROVIDER == "mistral":
        return MistralEmbedding()
    return OpenAIEmbedding()


# ----------------------------------------------------------------------------
# SparseEncoder (BM25 para el vector disperso de Qdrant)
# ----------------------------------------------------------------------------

class SparseEncoder:
    """BM25 vía fastembed; produce índices/valores para SparseVector de Qdrant."""
    def __init__(self):
        from fastembed import SparseTextEmbedding
        self.model = SparseTextEmbedding(model_name="Qdrant/bm25")

    def encode(self, texts: list[str]) -> list[tuple[list[int], list[float]]]:
        out = []
        for emb in self.model.embed(texts):
            out.append((emb.indices.tolist(), emb.values.tolist()))
        return out


# ----------------------------------------------------------------------------
# OcrProvider (parametrizable; stub por defecto)
# ----------------------------------------------------------------------------

@dataclass
class OcrResult:
    text: str
    extraction_method: str = "ocr"
    confidence: Optional[float] = None
    provider: str = "stub"


class OcrProvider(ABC):
    @abstractmethod
    def extract(self, file_path: str) -> OcrResult: ...


class StubOcr(OcrProvider):
    """No llama a ningún API. Marca el documento como OCR pendiente de proveedor
    real; devuelve texto vacío para que el pipeline lo registre y siga."""
    def extract(self, file_path: str) -> OcrResult:
        return OcrResult(text="", extraction_method="ocr", provider="stub")


class AzureOcr(OcrProvider):
    """Hueco para Azure AI Vision / Document Intelligence (Fase 1)."""
    def extract(self, file_path: str) -> OcrResult:
        raise NotImplementedError("Configurar Azure Document Intelligence en Fase 1")


def get_ocr_provider() -> OcrProvider:
    return {"stub": StubOcr, "azure": AzureOcr}.get(OCR_PROVIDER, StubOcr)()


# ----------------------------------------------------------------------------
# Orquestador (esqueleto; la lógica de extracción/chunking llega en Fases 1-2)
# ----------------------------------------------------------------------------

class IngestPipeline:
    def __init__(self):
        self.embedder = get_embedding_provider()
        self.sparse = SparseEncoder()
        self.ocr = get_ocr_provider()

    def index_chunks(self, chunks: list[Chunk]) -> int:
        """Embed (denso+sparse) y upsert en Qdrant. Devuelve nº indexado.
        La escritura en Postgres (metadatos + qdrant_point_id) la hace el
        llamador en la fase de registro, tras el upsert, para reconciliación."""
        if not chunks:
            return 0
        texts = [c.content for c in chunks]
        dense = self.embedder.embed(texts)
        sparse = self.sparse.encode(texts)
        for c, d, (si, sv) in zip(chunks, dense, sparse):
            c.dense_vector = d
            c.sparse_indices, c.sparse_values = si, sv
            c.qdrant_point_id = c.point_id
        # El upsert real a Qdrant se añade en Fase 3 (motor híbrido).
        return len(chunks)


if __name__ == "__main__":
    # Smoke test: verifica que los providers se instancian (sin llamar APIs).
    p = IngestPipeline()
    print(f"EmbeddingProvider: {type(p.embedder).__name__} (dims={p.embedder.dims})")
    print(f"SparseEncoder    : {type(p.sparse).__name__} (BM25 fastembed)")
    print(f"OcrProvider      : {type(p.ocr).__name__}")
    print("OK — esqueleto del pipeline listo.")
