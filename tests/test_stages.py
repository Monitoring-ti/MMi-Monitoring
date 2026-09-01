"""Tests etapas B2 (sin red)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from mmi.index.stages import (
    STAGE_ORDER,
    StageContext,
    chunks_from_pg,
    detect_resume_stage,
    hydrate_context_from_document,
    run_through_chunk,
    stage_chunk,
    stage_register,
    stage_validate,
)


def test_stage_order_includes_identity_register():
    assert "identity" in STAGE_ORDER
    assert "register" in STAGE_ORDER
    assert STAGE_ORDER.index("chunk") < STAGE_ORDER.index("embed")


def test_stage_validate_missing_file(tmp_path: Path):
    ctx = StageContext(path=tmp_path / "missing.pdf", document_key="DOC-1", tipo="guia")
    res = stage_validate(ctx)
    assert not res.ok
    assert "no existe" in res.reason


def test_run_through_chunk_skip_on_empty_extract(tmp_path: Path):
    f = tmp_path / "empty.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    ctx = StageContext(path=f, document_key="DOC-EMPTY", tipo="guia")
    with patch("mmi.index.store.pg_schema_v2", return_value=False):
        with patch("mmi.index.blocks.blocks_from_path", return_value=[]):
            results = run_through_chunk(ctx)
    assert results[-1].stage == "extract"
    assert not results[-1].ok


def test_stage_chunk_sets_content_hash():
    from mmi.index.chunking import ChunkOut

    ctx = StageContext(path=Path("doc.pdf"), document_key="K", tipo="guia")
    ctx.blocks = [type("B", (), {"content": "hello world" * 10})()]
    with patch("mmi.index.chunking.chunk_blocks") as mock_chunk:
        mock_chunk.return_value = [
            ChunkOut(
                content="chunk one",
                chunk_index=0,
                token_count=3,
                page_start=1,
                page_end=1,
                section_path="s1",
                criticality_level="normal",
                asset_codes=[],
            )
        ]
        res = stage_chunk(ctx)
    assert res.ok
    assert ctx.content_hash
    assert ctx.metrics["chunks"] == 1


def test_chunks_from_pg_maps_fields():
    rows = [
        {
            "content": "hello",
            "chunk_index": 0,
            "token_count": 2,
            "page_start": 1,
            "page_end": 1,
            "section_path": "s1",
            "criticality_level": "high",
            "asset_codes": ["P-101"],
            "qdrant_point_id": "pt-1",
        }
    ]
    chunks = chunks_from_pg(rows)
    assert len(chunks) == 1
    assert chunks[0].content == "hello"
    assert chunks[0].asset_codes == ["P-101"]


def test_stage_register_skips_when_document_id_set():
    ctx = StageContext(path=Path("doc.pdf"), document_key="K", tipo="guia", document_id="doc-uuid")
    with patch("mmi.index.store.pg_schema_v2", return_value=True):
        with patch("mmi.index.store.pg_get_document", return_value={"catalog_id": "cat-1", "tenant_id": "t-1"}):
            res = stage_register(ctx)
    assert res.ok
    assert res.next_stage == "embed"
    assert ctx.catalog_id == "cat-1"


def test_detect_resume_stage_no_chunks():
    with patch("mmi.index.store.pg_get_document", return_value={"id": "d1", "status": "failed"}):
        with patch("mmi.index.store.pg_count_chunks", return_value=0):
            assert detect_resume_stage("d1") == "extract"


def test_detect_resume_stage_partial_qdrant():
    with patch("mmi.index.store.pg_get_document", return_value={"id": "d1", "status": "failed"}):
        with patch("mmi.index.store.pg_count_chunks", return_value=10):
            with patch("mmi.index.store.pg_chunk_point_ids", return_value=["p1"]):
                assert detect_resume_stage("d1") == "embed"


def test_hydrate_context_loads_chunks():
    ctx = StageContext(path=Path("doc.pdf"), document_key="K", tipo="guia")
    doc = {
        "id": "d1",
        "catalog_id": "c1",
        "tenant_id": "t1",
        "document_key": "K",
        "source_file_id": str(Path("doc.pdf").resolve()),
    }
    rows = [{"content": "x", "chunk_index": 0, "token_count": 1}]
    with patch("mmi.index.store.pg_load_chunks", return_value=rows):
        hydrate_context_from_document(ctx, doc)
    assert ctx.document_id == "d1"
    assert len(ctx.chunks) == 1
