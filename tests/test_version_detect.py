"""Tests de logical_key y resolución R1–R4."""

from __future__ import annotations

from mmi.catalog.logical_key import DocumentIdentityMeta, derive_logical_key
from mmi.catalog.version_detect import (
    DocumentCandidate,
    IdentityRegistry,
    KnownVersion,
    resolve_decision,
    resolve_ingest_decision,
)


def test_derive_logical_key_with_codigo():
    meta = DocumentIdentityMeta(
        tenant_slug="monitoring",
        origen="ods1",
        name="ANEXO A CHECK LIST SIST ENFR CTS DCH REV 1.xlsx",
        relative_path="07 ENTREGABLES/E02 CHECK LIST/6. REV 1/ANEXO A CHECK LIST SIST ENFR CTS DCH REV 1.xlsx",
        tipo_documental="tabla",
        codigo_documento="",
        modulo="DCH",
    )
    meta.codigo_documento = "SGP-07MYC-GUIGS-00001"
    key = derive_logical_key(meta)
    assert "sgp 07myc guigs 00001" in key.lower()
    assert key.startswith("monitoring|")


def test_r1_duplicado_fisico():
    reg = IdentityRegistry()
    reg.register(
        KnownVersion(
            logical_key="monitoring|guia-a",
            file_hash="abc123",
            content_hash="content1",
            name="guia.pdf",
            path="/tmp/guia.pdf",
        )
    )
    candidate = DocumentCandidate(
        name="guia.pdf",
        path="/tmp/copy/guia.pdf",
        file_hash="abc123",
        logical_key="monitoring|guia-a",
        content_hash="content1",
        identity=DocumentIdentityMeta(name="guia.pdf"),
    )
    decision = resolve_decision(candidate, reg)
    assert decision.kind == "duplicado_fisico"
    assert not decision.index


def test_r2_nueva_version():
    reg = IdentityRegistry()
    reg.register(
        KnownVersion(
            logical_key="monitoring|sgp-07myc-guigs-00001",
            file_hash="hash_v1",
            content_hash="content_v1",
            name="GUIGS Rev 4.pdf",
            path="/tmp/rev4.pdf",
            codigo_documento="SGP-07MYC-GUIGS-00001",
            confidence="high",
        )
    )
    candidate = DocumentCandidate(
        name="GUIGS Rev 6.pdf",
        path="/tmp/rev6.pdf",
        file_hash="hash_v2",
        logical_key="monitoring|sgp-07myc-guigs-00001",
        content_hash="content_v2",
        identity=DocumentIdentityMeta(
            name="GUIGS Rev 6.pdf",
            codigo_documento="SGP-07MYC-GUIGS-00001",
        ),
        confidence="high",
    )
    decision = resolve_decision(candidate, reg)
    assert decision.kind == "nueva_version"
    assert decision.index


def test_resolve_ingest_decision_mismo_contenido():
    reg = IdentityRegistry()
    reg.register(
        KnownVersion(
            logical_key="monitoring|sgp 07myc guigs 00001",
            file_hash="hash_v1",
            content_hash="same_content",
            name="GUIGS Rev 4.pdf",
            path="/tmp/rev4.pdf",
            document_id="doc-1",
            confidence="high",
        )
    )
    candidate = DocumentCandidate(
        name="GUIGS copy.pdf",
        path="/tmp/copy.pdf",
        file_hash="hash_v2",
        logical_key="monitoring|sgp 07myc guigs 00001",
        content_hash=None,
        identity=DocumentIdentityMeta(name="GUIGS copy.pdf"),
        confidence="high",
    )
    decision = resolve_ingest_decision(
        candidate,
        content_hash_value="same_content",
        registry=reg,
    )
    assert decision.kind == "mismo_contenido"
    assert not decision.index


def test_r4_needs_review_same_codigo_different_asset():
    reg = IdentityRegistry()
    reg.register(
        KnownVersion(
            logical_key="monitoring|ods1|ncc-030|ct-01|guia|dch",
            file_hash="h1",
            content_hash="c1",
            name="Manual.pdf",
            path="/a/Manual.pdf",
            codigo_documento="NCC-030",
            asset_tag="CT-01",
            confidence="high",
        )
    )
    candidate = DocumentCandidate(
        name="Manual.pdf",
        path="/b/Manual.pdf",
        file_hash="h2",
        logical_key="monitoring|ods1|ncc-030|ct-02|guia|dch",
        content_hash="c2",
        identity=DocumentIdentityMeta(
            name="Manual.pdf",
            codigo_documento="NCC-030",
            asset_tag="CT-02",
        ),
        confidence="high",
    )
    decision = resolve_decision(candidate, reg)
    assert decision.kind == "needs_review"
    assert not decision.index
