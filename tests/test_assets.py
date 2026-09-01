"""Tests catálogo EAM (heurística sin Supabase)."""

from pathlib import Path
from unittest.mock import patch

from mmi.catalog.assets import (
    CatalogAsset,
    collect_asset_tags_from_manifest,
    enrich_manifest_asset_tags,
    validate_manifest_catalog,
)
from mmi.catalog.logical_key import extract_asset_tag


def test_extract_asset_tag_from_filename():
    tag = extract_asset_tag(
        "4400285992-06500-100EL-00001 Equipos Sala eléctrica.pdf",
        "ODS1 TORR ENF DCH/04 INGENIERIA/ELECTRICO",
    )
    assert tag


def test_enrich_manifest_asset_tags_idempotent(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        """{
  "files": [{
    "name": "SGP-07MYC-GUIGS-00001 Rev 5.pdf",
    "relative_path": "ODS1 TORR ENF DCH/00 DOCUMENTOS NCC30/3. REFERENCIA ANEXOS/SGP-07MYC-GUIGS-00001 Rev 5.pdf",
    "include_in_analysis": true,
    "suggested_tipo": "guia"
  }]
}""",
        encoding="utf-8",
    )
    n1 = enrich_manifest_asset_tags(manifest_path)
    n2 = enrich_manifest_asset_tags(manifest_path)
    assert n1 >= 1
    assert n2 == 0
    grouped = collect_asset_tags_from_manifest(manifest_path)
    assert grouped


def test_validate_manifest_catalog_with_mock_catalog(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        """{
  "files": [
    {"name": "doc1.pdf", "relative_path": "ODS1/DCH", "include_in_analysis": true, "asset_tag": "P-101"},
    {"name": "doc2.pdf", "relative_path": "ODS1/DCH", "include_in_analysis": true, "asset_tag": "UNKNOWN"},
    {"name": "readme.pdf", "relative_path": "misc", "include_in_analysis": true}
  ]
}""",
        encoding="utf-8",
    )
    catalog = {
        "P-101": CatalogAsset(id="1", asset_tag="P-101", modulo="ODS1", vigente=True),
    }
    with patch("mmi.catalog.assets.load_assets", return_value=catalog):
        report = validate_manifest_catalog(manifest_path, assets=catalog)
    s = report["summary"]
    assert s["entries_included"] == 3
    assert s["with_asset_tag"] == 2
    assert s["valid_tags"] == 1
    assert s["unknown_tags"] == 1
    assert "UNKNOWN" in report["unknown_tags"]
