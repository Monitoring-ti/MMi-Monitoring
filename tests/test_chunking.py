"""Tests de límites de chunking para embeddings."""

from mmi.index.chunking import MAX_EMBED_TOKENS, ChunkOut, enforce_max_embed_size, split_oversized_text


def test_split_oversized_text_splits_large_paragraph():
    text = "palabra " * 20_000
    parts = split_oversized_text(text)
    assert len(parts) > 1
    assert all(len(p) > 0 for p in parts)
    assert all(len(p.split()) <= 20_000 for p in parts)


def test_enforce_max_embed_size_splits_chunk():
    huge = "x " * 50_000
    chunks = [
        ChunkOut(
            content=huge,
            chunk_index=0,
            token_count=50_000,
            section_path="Tabla FMECA",
        )
    ]
    out = enforce_max_embed_size(chunks)
    assert len(out) > 1
    assert all(c.token_count <= MAX_EMBED_TOKENS for c in out)
    assert [c.chunk_index for c in out] == list(range(len(out)))
