"""Catálogo documental: identidad lógica y detección de versiones."""

from mmi.catalog.assets import (
    CatalogAsset,
    collect_asset_tags_from_manifest,
    enrich_manifest_asset_tags,
    load_assets,
    seed_catalog_from_manifest,
    validate_asset_tag,
    validate_manifest_catalog,
)
from mmi.catalog.logical_key import DocumentIdentityMeta, derive_logical_key
from mmi.catalog.version_detect import (
    DocumentCandidate,
    IdentityRegistry,
    VersionDecision,
    load_registry_from_supabase,
    resolve_decision,
    resolve_ingest_decision,
    scan_manifest,
)

__all__ = [
    "CatalogAsset",
    "collect_asset_tags_from_manifest",
    "DocumentCandidate",
    "DocumentIdentityMeta",
    "IdentityRegistry",
    "VersionDecision",
    "derive_logical_key",
    "enrich_manifest_asset_tags",
    "load_assets",
    "seed_catalog_from_manifest",
    "validate_asset_tag",
    "validate_manifest_catalog",
    "load_registry_from_supabase",
    "resolve_decision",
    "resolve_ingest_decision",
    "scan_manifest",
]
