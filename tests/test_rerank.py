"""Tests reranker léxico C1 (sin red)."""

from mmi.search.engine import SearchResult
from mmi.search.rerank import (
    compute_rerank_score,
    extract_exact_tags,
    lexical_overlap,
    rerank_results,
)


def _result(titulo: str, content: str, score: float = 0.5) -> SearchResult:
    return SearchResult(
        point_id="p1",
        score=score,
        content=content,
        document_id="d1",
        tipo="guia",
        dominio=None,
        criticality_level="normal",
        section_path=None,
        page_start=1,
        page_end=1,
        asset_codes=[],
        chunk_index=0,
        titulo=titulo,
        citation=titulo,
    )


def test_extract_exact_tags():
    tags = extract_exact_tags("SGP-07MYC-GUIGS-00001 y TE-401A FMECA")
    assert any("GUIGS" in t.upper() for t in tags)
    assert any("TE-401" in t.upper() for t in tags)


def test_lexical_overlap():
    assert lexical_overlap("FMECA modos falla", "ANEXO FMECA modos de falla sistema") > 0.5


def test_rerank_promotes_exact_tag_match():
    query = "ANEXO A FMECA MEC REEMP SIST ENFR CTS DCH"
    weak = _result("documento genérico", "texto varios", score=0.9)
    strong = _result(
        "ANEXO A FMECA MEC REEMP SIST ENFR CTS DCH ODS 1",
        "modos de falla",
        score=0.4,
    )
    assert compute_rerank_score(query, strong) > compute_rerank_score(query, weak)


def test_asset_code_boost():
    query = "activo CTS-DCH-ENF enfriamiento"
    plain = _result("doc", "contenido", score=0.5)
    tagged = _result("doc", "contenido", score=0.5)
    tagged.asset_codes = ["CTS-DCH-ENF"]
    assert compute_rerank_score(query, tagged) > compute_rerank_score(query, plain)
