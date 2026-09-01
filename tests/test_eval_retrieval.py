"""Tests golden set C3 (métricas sin red)."""

import json
from pathlib import Path

from mmi.eval.retrieval import (
    aggregate_metrics,
    is_relevant_hit,
    load_golden_cases,
    recall_at_k,
    reciprocal_rank,
)
from mmi.search.engine import SearchResult


def _hit(titulo: str, content: str = "", tipo: str = "guia") -> SearchResult:
    return SearchResult(
        point_id="p1",
        score=0.9,
        content=content,
        document_id="d1",
        tipo=tipo,
        dominio="mantenibilidad",
        criticality_level="normal",
        section_path=None,
        page_start=1,
        page_end=2,
        asset_codes=[],
        chunk_index=0,
        titulo=titulo,
        citation=titulo,
    )


def test_load_golden_cases():
    path = Path("fixtures/golden-set-retrieval.json")
    cases = load_golden_cases(path)
    assert len(cases) >= 30
    motor = [c for c in cases if c.get("category") == "motor"]
    assert len(motor) >= 5


def test_is_relevant_hit_titulo_any():
    hit = _hit("ANEXO A FMECA MEC REEMP SIST ENFR CTS DCH")
    spec = {"titulo_any": ["FMECA", "ENFR"]}
    assert is_relevant_hit(hit, spec)


def test_recall_at_k_and_mrr():
    hits = [
        _hit("documento irrelevante"),
        _hit("ANEXO A FMECA sistema enfriamiento", content="modos de falla"),
    ]
    spec = {"titulo_any": ["FMECA"]}
    assert recall_at_k(hits, spec, 1) == 0.0
    assert recall_at_k(hits, spec, 5) == 1.0
    assert reciprocal_rank(hits, spec) == 0.5


def test_aggregate_metrics():
    rows = [
        {"category": "motor", "mrr": 1.0, "recall@1": 1.0, "recall@3": 1.0, "recall@5": 1.0, "precision@1": 1.0, "precision@3": 0.33, "precision@5": 0.2},
        {"category": "guia", "mrr": 0.5, "recall@1": 0.0, "recall@3": 1.0, "recall@5": 1.0, "precision@1": 0.0, "precision@3": 0.33, "precision@5": 0.2},
    ]
    agg = aggregate_metrics(rows, k_values=[1, 3, 5])
    assert agg["total"] == 2
    assert agg["mrr"] == 0.75
    assert "motor" in agg["by_category"]


def test_build_query_motor_case():
    from mmi.tools.eval_retrieval import _build_query

    case = {
        "category": "motor",
        "asset_id": "CTS-DCH-ENF",
        "symptom": "alta temperatura",
        "query": "ignored",
    }
    q = _build_query(case)
    assert "alta temperatura" in q
    assert "CTS-DCH-ENF" in q or "enfriamiento" in q.lower()


def test_golden_set_json_valid():
    data = json.loads(Path("fixtures/golden-set-retrieval.json").read_text(encoding="utf-8"))
    assert data.get("version")
    for case in data["cases"]:
        assert case.get("id")
        assert case.get("query") or case.get("symptom")
        assert case.get("category")
        assert case.get("relevant")
