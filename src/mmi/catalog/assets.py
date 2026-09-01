"""Catálogo EAM/CMMS: carga, validación y enriquecimiento de asset_tag en manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mmi.catalog.logical_key import DocumentIdentityMeta, extract_asset_tag
from mmi.index.store import pg_get_tenant_id, pg_headers, pg_rest


@dataclass(frozen=True)
class CatalogAsset:
    id: str
    asset_tag: str
    modulo: str | None = None
    codigo_tecnico: str | None = None
    vigente: bool = True


def pg_list_catalog_assets(tenant_id: str) -> list[dict[str, Any]]:
    r = __import__("requests").get(
        f"{pg_rest()}/catalog_assets",
        params={
            "tenant_id": f"eq.{tenant_id}",
            "select": "id,asset_tag,modulo,codigo_tecnico,vigente",
            "order": "asset_tag",
        },
        headers=pg_headers(),
        timeout=60,
    )
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return r.json()


def pg_upsert_catalog_asset(
    tenant_id: str,
    asset_tag: str,
    *,
    modulo: str | None = None,
    codigo_tecnico: str | None = None,
    vigente: bool = True,
) -> dict[str, Any]:
    tag = asset_tag.strip().upper()
    payload = {
        "tenant_id": tenant_id,
        "asset_tag": tag,
        "modulo": modulo,
        "codigo_tecnico": codigo_tecnico,
        "vigente": vigente,
    }
    r = __import__("requests").post(
        f"{pg_rest()}/catalog_assets",
        params={"on_conflict": "tenant_id,asset_tag"},
        headers={**pg_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else payload


def load_assets(*, tenant_slug: str = "monitoring") -> dict[str, CatalogAsset]:
    tenant_id = pg_get_tenant_id(tenant_slug)
    out: dict[str, CatalogAsset] = {}
    for row in pg_list_catalog_assets(tenant_id):
        tag = (row.get("asset_tag") or "").strip().upper()
        if not tag:
            continue
        out[tag] = CatalogAsset(
            id=str(row["id"]),
            asset_tag=tag,
            modulo=row.get("modulo"),
            codigo_tecnico=row.get("codigo_tecnico"),
            vigente=bool(row.get("vigente", True)),
        )
    return out


def validate_asset_tag(tag: str, assets: dict[str, CatalogAsset] | None = None) -> bool:
    normalized = tag.strip().upper()
    if not normalized:
        return False
    catalog = assets if assets is not None else load_assets()
    row = catalog.get(normalized)
    return row is not None and row.vigente


def collect_asset_tags_from_manifest(manifest_path: Path) -> dict[str, set[str]]:
    """Extrae asset_tag candidatos agrupados por módulo inferido."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_modulo: dict[str, set[str]] = {}
    for entry in manifest.get("files") or []:
        if entry.get("include_in_analysis") is False:
            continue
        meta = DocumentIdentityMeta.from_manifest_entry(entry)
        tag = (entry.get("asset_tag") or meta.asset_tag or "").strip().upper()
        if not tag:
            tag = extract_asset_tag(entry.get("name") or "", entry.get("relative_path") or "").upper()
        if not tag or len(tag) < 3:
            continue
        modulo = (entry.get("modulo") or meta.modulo or "ODS1").upper()
        by_modulo.setdefault(modulo, set()).add(tag)
    return by_modulo


def enrich_manifest_asset_tags(manifest_path: Path, *, write: bool = True) -> int:
    """B4.1 — rellena asset_tag/modulo/codigo_documento/numero_guia vacíos."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changed = 0
    for entry in manifest.get("files") or []:
        if entry.get("include_in_analysis") is False:
            continue
        meta = DocumentIdentityMeta.from_manifest_entry(entry)
        before = {
            "asset_tag": entry.get("asset_tag"),
            "modulo": entry.get("modulo"),
            "codigo_documento": entry.get("codigo_documento"),
            "numero_guia": entry.get("numero_guia"),
        }
        if not entry.get("asset_tag") and meta.asset_tag:
            entry["asset_tag"] = meta.asset_tag
        if not entry.get("modulo") and meta.modulo:
            entry["modulo"] = meta.modulo
        if not entry.get("codigo_documento") and meta.codigo_documento:
            entry["codigo_documento"] = meta.codigo_documento
        if not entry.get("numero_guia") and meta.numero_guia:
            entry["numero_guia"] = meta.numero_guia
        after = {
            "asset_tag": entry.get("asset_tag"),
            "modulo": entry.get("modulo"),
            "codigo_documento": entry.get("codigo_documento"),
            "numero_guia": entry.get("numero_guia"),
        }
        if after != before:
            changed += 1
    if write and changed:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return changed


def validate_manifest_catalog(
    manifest_path: Path,
    *,
    tenant_slug: str = "monitoring",
    assets: dict[str, CatalogAsset] | None = None,
) -> dict[str, Any]:
    """B4.3 — cruza asset_tag del manifest con catalog_assets."""
    catalog = assets
    if catalog is None:
        try:
            catalog = load_assets(tenant_slug=tenant_slug)
        except RuntimeError:
            catalog = {}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    unknown_tags: set[str] = set()
    by_modulo: dict[str, dict[str, int]] = {}
    stats = {
        "entries_included": 0,
        "with_asset_tag": 0,
        "without_asset_tag": 0,
        "valid_tags": 0,
        "unknown_tags": 0,
        "catalog_size": len(catalog),
    }

    for entry in manifest.get("files") or []:
        if entry.get("include_in_analysis") is False:
            continue
        stats["entries_included"] += 1
        meta = DocumentIdentityMeta.from_manifest_entry(entry)
        tag = (entry.get("asset_tag") or meta.asset_tag or "").strip().upper()
        modulo = (entry.get("modulo") or meta.modulo or "ODS1").upper()
        mod_stats = by_modulo.setdefault(modulo, {"total": 0, "valid": 0, "unknown": 0, "empty": 0})
        mod_stats["total"] += 1

        if not tag:
            stats["without_asset_tag"] += 1
            mod_stats["empty"] += 1
            rows.append(
                {
                    "name": entry.get("name"),
                    "relative_path": entry.get("relative_path"),
                    "modulo": modulo,
                    "asset_tag": "",
                    "status": "sin_tag",
                }
            )
            continue

        stats["with_asset_tag"] += 1
        ok = bool(catalog) and validate_asset_tag(tag, catalog)
        if ok:
            stats["valid_tags"] += 1
            mod_stats["valid"] += 1
            status = "ok"
        else:
            stats["unknown_tags"] += 1
            mod_stats["unknown"] += 1
            unknown_tags.add(tag)
            status = "unknown"

        rows.append(
            {
                "name": entry.get("name"),
                "relative_path": entry.get("relative_path"),
                "modulo": modulo,
                "asset_tag": tag,
                "codigo_documento": entry.get("codigo_documento") or meta.codigo_documento,
                "status": status,
            }
        )

    coverage = (
        round(stats["valid_tags"] / stats["with_asset_tag"], 3) if stats["with_asset_tag"] else 0.0
    )
    return {
        "tenant": tenant_slug,
        "manifest": str(manifest_path),
        "summary": {
            **stats,
            "unknown_tag_count": len(unknown_tags),
            "coverage": coverage,
            "by_modulo": by_modulo,
        },
        "unknown_tags": sorted(unknown_tags),
        "issues": [r for r in rows if r["status"] != "ok"][:200],
        "entries": rows,
    }


def seed_catalog_from_manifest(
    manifest_path: Path,
    *,
    tenant_slug: str = "monitoring",
    dry_run: bool = False,
) -> list[str]:
    """Inserta tags únicos del manifest en catalog_assets (stub EAM)."""
    tenant_id = pg_get_tenant_id(tenant_slug)
    grouped = collect_asset_tags_from_manifest(manifest_path)
    inserted: list[str] = []
    for modulo, tags in sorted(grouped.items()):
        for tag in sorted(tags):
            if dry_run:
                inserted.append(tag)
                continue
            pg_upsert_catalog_asset(tenant_id, tag, modulo=modulo)
            inserted.append(tag)
    return inserted
