"""Embeddings densos (OpenAI) y dispersos (BM25)."""

from __future__ import annotations

import os

from openai import OpenAI

EMBED_MODEL = os.environ.get("MMI_OPENAI_EMBED_MODEL", "text-embedding-3-small")
DENSE_DIMS = 1536


class OpenAIEmbedding:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = EMBED_MODEL

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]

    @property
    def dims(self) -> int:
        return DENSE_DIMS


class SparseEncoder:
    """BM25 vía fastembed; si onnxruntime falla (Windows), devuelve vacío."""

    def __init__(self) -> None:
        self._model = None
        self._ok: bool | None = None

    def _ready(self) -> bool:
        if self._ok is False:
            return False
        if self._model is None:
            try:
                from fastembed import SparseTextEmbedding

                self._model = SparseTextEmbedding(model_name="Qdrant/bm25")
                self._ok = True
            except Exception as exc:  # noqa: BLE001
                print(f"[mmi] BM25 sparse desactivado: {exc}")
                self._ok = False
        return bool(self._ok)

    def encode(self, texts: list[str]) -> list[tuple[list[int], list[float]]]:
        if not self._ready() or not texts:
            return [([], []) for _ in texts]
        return [(emb.indices.tolist(), emb.values.tolist()) for emb in self._model.embed(texts)]
