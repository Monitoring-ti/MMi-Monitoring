"""Tests grafo de conocimiento (sin red)."""

from mmi.graph.builder import GraphBuilder, _hit_to_chunk_node
from mmi.graph.models import GraphPayload
from mmi.search.engine import SearchResult


class _FakeEngine:
    _tenant_id = "tenant-1"
    collection = "mmi"


def _sample_hit(**overrides) -> SearchResult:
    base = dict(
        point_id="pt-1",
        score=0.88,
        content="FMECA modo falla enfriamiento",
        document_id="doc-1",
        tipo="guia",
        dominio="mantenibilidad",
        criticality_level="normal",
        section_path=None,
        page_start=3,
        page_end=3,
        asset_codes=["CTS-DCH"],
        chunk_index=0,
        titulo="FMECA Enfriamiento",
        version_label="vigente",
        document_key="FMECA-ENFR",
        citation="FMECA Enfriamiento — pág. 3",
    )
    base.update(overrides)
    return SearchResult(**base)


def test_build_from_hits_creates_chunk_document_asset():
    builder = GraphBuilder(_FakeEngine())  # type: ignore[arg-type]
    payload = builder._build_from_hits([_sample_hit()], min_similarity=0.5)
    kinds = {n.kind for n in payload.nodes}
    assert "chunk" in kinds
    assert "document" in kinds
    assert "asset" in kinds
    assert len(payload.edges) >= 2


def test_view_documents_hides_assets():
    builder = GraphBuilder(_FakeEngine())  # type: ignore[arg-type]
    payload = builder._build_from_hits([_sample_hit()], min_similarity=0.5, view="documents")
    assert all(n.kind in {"chunk", "document"} for n in payload.nodes)


def test_apply_filters_by_dominio():
    builder = GraphBuilder(_FakeEngine())  # type: ignore[arg-type]
    hits = [
        _sample_hit(point_id="a", dominio="mantenibilidad"),
        _sample_hit(point_id="b", dominio="confiabilidad", document_id="doc-2"),
    ]
    filtered = builder._apply_filters(hits, {"dominio": "mantenibilidad"})
    assert len(filtered) == 1
    assert filtered[0].point_id == "a"


def test_chunk_node_label_includes_page():
    node = _hit_to_chunk_node(_sample_hit())
    assert "p.3" in node.label
