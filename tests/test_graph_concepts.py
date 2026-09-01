"""Tests extracción conceptos FMECA."""

from mmi.graph.concepts import extract_concepts_from_hit
from mmi.search.engine import SearchResult


def _hit(**kw) -> SearchResult:
    base = dict(
        point_id="p1",
        score=0.9,
        content="",
        document_id="d1",
        tipo="tabla",
        dominio="mantenibilidad",
        criticality_level="normal",
        section_path=None,
        page_start=1,
        page_end=1,
        asset_codes=[],
        chunk_index=0,
        titulo="FMECA sistema",
    )
    base.update(kw)
    return SearchResult(**base)


def test_extract_modo_falla():
    hit = _hit(content="Modo de falla: pérdida de sellado en intercambiador")
    concepts = extract_concepts_from_hit(hit)
    assert any("sellado" in c[1].lower() for c in concepts)


def test_extract_rpn():
    hit = _hit(content="FMECA fila 3 RPN: 128 criticidad alta")
    concepts = extract_concepts_from_hit(hit)
    assert any(c[2] == "rpn" for c in concepts)
