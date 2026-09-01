"""Detección de duplicados físicos, revisiones y conflictos de identidad (R1–R4)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from mmi.analysis.status import _find_extract_dir
from mmi.catalog.logical_key import (
    DocumentIdentityMeta,
    derive_logical_key,
    extract_codigo_documento,
    identity_confidence,
    normalize_title,
)
from mmi.index.chunking import file_sha256
from mmi.index.content_hash import content_hash

DecisionKind = Literal[
    "duplicado_fisico",
    "mismo_contenido",
    "nueva_version",
    "nuevo_documento",
    "needs_review",
]


@dataclass
class KnownVersion:
    logical_key: str
    file_hash: str
    content_hash: str | None
    name: str
    path: str
    document_id: str | None = None
    catalog_id: str | None = None
    version_label: str = ""
    asset_tag: str = ""
    codigo_documento: str = ""
    confidence: str = "medium"


@dataclass
class DocumentCandidate:
    name: str
    path: str
    file_hash: str
    logical_key: str
    content_hash: str | None
    identity: DocumentIdentityMeta
    confidence: str = "medium"
    version_label: str = ""
    relative_path: str = ""

    @classmethod
    def from_ingest(
        cls,
        path: Path,
        *,
        tenant_slug: str = "monitoring",
        tipo: str = "otro",
        document_key: str | None = None,
        version_label: str | None = None,
        origen: str = "local",
        relative_path: str = "",
        asset_tag: str = "",
        modulo: str = "",
    ) -> DocumentCandidate:
        entry = {
            "name": path.name,
            "absolute_path": str(path.resolve()),
            "relative_path": relative_path,
            "suggested_tipo": tipo,
            "document_key": document_key or "",
            "revision": version_label or "",
            "source": origen,
            "asset_tag": asset_tag,
            "modulo": modulo,
        }
        identity = DocumentIdentityMeta.from_manifest_entry(entry, tenant_slug=tenant_slug)
        logical_key = derive_logical_key(identity)
        conf = identity_confidence(identity, logical_key)
        return cls(
            name=path.name,
            path=str(path.resolve()),
            file_hash=file_sha256(path),
            logical_key=logical_key,
            content_hash=None,
            identity=identity,
            confidence=conf,
            version_label=(version_label or "").strip(),
            relative_path=relative_path,
        )

    @classmethod
    def from_manifest_entry(
        cls,
        entry: dict,
        *,
        tenant_slug: str = "monitoring",
        extract_root: Path | None = None,
    ) -> DocumentCandidate | None:
        abs_path = entry.get("absolute_path")
        if not abs_path:
            return None
        path = Path(abs_path)
        if not path.exists():
            return None

        identity = DocumentIdentityMeta.from_manifest_entry(entry, tenant_slug=tenant_slug)
        logical_key = derive_logical_key(identity)
        conf = identity_confidence(identity, logical_key)

        c_hash: str | None = None
        if extract_root:
            extract_dir = _find_extract_dir(extract_root, abs_path)
            if extract_dir:
                c_hash = content_hash_from_extract_dir(extract_dir)

        return cls(
            name=entry.get("name") or path.name,
            path=str(path.resolve()),
            file_hash=file_sha256(path),
            logical_key=logical_key,
            content_hash=c_hash,
            identity=identity,
            confidence=conf,
            version_label=(entry.get("revision") or entry.get("version_label") or "").strip(),
            relative_path=entry.get("relative_path") or "",
        )


@dataclass
class VersionDecision:
    kind: DecisionKind
    name: str
    path: str
    file_hash: str
    logical_key: str
    content_hash: str | None = None
    confidence: str = "medium"
    index: bool = False
    reason: str = ""
    supersedes_document_id: str | None = None
    existing_document_id: str | None = None
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class IdentityRegistry:
    def __init__(self) -> None:
        self.by_file_hash: dict[str, KnownVersion] = {}
        self.by_logical_key: dict[str, KnownVersion] = {}
        self.by_filename: dict[str, list[KnownVersion]] = {}

    def register(self, rec: KnownVersion) -> None:
        self.by_file_hash[rec.file_hash] = rec
        prev = self.by_logical_key.get(rec.logical_key)
        if not prev or (rec.content_hash and prev.content_hash != rec.content_hash):
            self.by_logical_key[rec.logical_key] = rec
        self.by_filename.setdefault(rec.name.lower(), []).append(rec)

    def check_identity_conflict(self, candidate: DocumentCandidate) -> str | None:
        codigo = candidate.identity.codigo_documento or extract_codigo_documento(
            candidate.name, candidate.relative_path
        )
        if codigo:
            for key, rec in self.by_logical_key.items():
                if rec.codigo_documento == codigo and key != candidate.logical_key:
                    if candidate.identity.asset_tag and rec.asset_tag:
                        if candidate.identity.asset_tag != rec.asset_tag:
                            return (
                                f"mismo código {codigo}, activos distintos "
                                f"({candidate.identity.asset_tag} vs {rec.asset_tag})"
                            )
                    if candidate.confidence == "low" or rec.confidence == "low":
                        return f"mismo código {codigo}, logical_key distinto ({key})"

        same_name = self.by_filename.get(candidate.name.lower(), [])
        for rec in same_name:
            if rec.file_hash == candidate.file_hash:
                continue
            if rec.logical_key != candidate.logical_key and candidate.confidence == "low":
                return (
                    f"mismo nombre de archivo, identidad incierta "
                    f"({rec.logical_key} vs {candidate.logical_key})"
                )

        titulo = normalize_title(candidate.name)
        if titulo and candidate.confidence == "low":
            for rec in self.by_logical_key.values():
                if normalize_title(rec.name) == titulo and rec.logical_key != candidate.logical_key:
                    return (
                        f"título similar, logical_key distinto "
                        f"({rec.logical_key} vs {candidate.logical_key})"
                    )
        return None


def content_hash_from_extract_dir(extract_dir: Path) -> str | None:
    md_path = extract_dir / "extracted.md"
    if md_path.exists():
        try:
            return content_hash(md_path.read_text(encoding="utf-8"))
        except OSError:
            pass
    meta_path = extract_dir / "extracted.json"
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    parts: list[str] = []
    for key in ("format", "quality", "source_path"):
        val = data.get(key)
        if val:
            parts.append(str(val))
    meta = data.get("meta") or {}
    if isinstance(meta, dict):
        for key in ("file_name", "record_count", "sheet_count", "page_count", "slide_count"):
            val = meta.get(key)
            if val is not None:
                parts.append(f"{key}:{val}")
    sheets = data.get("sheets") or data.get("pages") or data.get("slides") or []
    if isinstance(sheets, list):
        for item in sheets[:50]:
            if isinstance(item, dict):
                for text_key in ("name", "title", "text", "markdown"):
                    val = item.get(text_key)
                    if val:
                        parts.append(str(val)[:500])
    if not parts:
        return None
    return content_hash("\n".join(parts))


def resolve_decision(candidate: DocumentCandidate, registry: IdentityRegistry) -> VersionDecision:
    base = {
        "name": candidate.name,
        "path": candidate.path,
        "file_hash": candidate.file_hash,
        "logical_key": candidate.logical_key,
        "content_hash": candidate.content_hash,
        "confidence": candidate.confidence,
    }

    hit = registry.by_file_hash.get(candidate.file_hash)
    if hit:
        return VersionDecision(
            kind="duplicado_fisico",
            index=False,
            reason="file_hash ya registrado (R1)",
            existing_document_id=hit.document_id,
            details={"matched_path": hit.path},
            **base,
        )

    conflict = registry.check_identity_conflict(candidate)
    if conflict:
        return VersionDecision(
            kind="needs_review",
            index=False,
            reason=conflict,
            details={"rule": "R4"},
            **base,
        )

    existing = registry.by_logical_key.get(candidate.logical_key)
    if not existing:
        return VersionDecision(
            kind="nuevo_documento",
            index=True,
            reason="logical_key nuevo (R3/R5)",
            **base,
        )

    if candidate.content_hash and existing.content_hash:
        if candidate.content_hash == existing.content_hash:
            return VersionDecision(
                kind="mismo_contenido",
                index=False,
                reason="logical_key igual, content_hash igual — skip embed",
                existing_document_id=existing.document_id,
                details={"rule": "R2-skip"},
                **base,
            )
        return VersionDecision(
            kind="nueva_version",
            index=True,
            reason="logical_key igual, content_hash distinto (R2)",
            supersedes_document_id=existing.document_id,
            existing_document_id=existing.document_id,
            details={"rule": "R2", "previous_file_hash": existing.file_hash[:12]},
            **base,
        )

    if candidate.confidence == "low":
        return VersionDecision(
            kind="needs_review",
            index=False,
            reason="logical_key existente pero sin content_hash para comparar (R4)",
            existing_document_id=existing.document_id,
            details={"rule": "R4-no-content-hash"},
            **base,
        )

    return VersionDecision(
        kind="nueva_version",
        index=True,
        reason="logical_key existente, asumir nueva versión (sin content_hash previo)",
        supersedes_document_id=existing.document_id,
        existing_document_id=existing.document_id,
        **base,
    )


def resolve_ingest_decision(
    candidate: DocumentCandidate,
    *,
    content_hash_value: str,
    tenant_slug: str = "monitoring",
    registry: IdentityRegistry | None = None,
) -> VersionDecision:
    """Resuelve R1–R4 para ingesta con content_hash ya calculado del chunking."""
    candidate.content_hash = content_hash_value
    reg = registry or load_registry_from_supabase(tenant_slug)
    return resolve_decision(candidate, reg)


def load_registry_from_supabase(tenant_slug: str = "monitoring") -> IdentityRegistry:
    registry = IdentityRegistry()
    try:
        from mmi.index.store import pg_get_tenant_id, pg_list_documents
    except ImportError:
        return registry

    try:
        tenant_id = pg_get_tenant_id(tenant_slug)
        rows = pg_list_documents(
            tenant_id,
            select=(
                "id,catalog_id,titulo,file_hash,content_hash,document_key,"
                "version_label,status,is_current,source_file_id"
            ),
        )
    except Exception:
        return registry

    logical_best: dict[str, tuple[tuple[int, ...], KnownVersion]] = {}
    for row in rows:
        if row.get("status") == "failed":
            continue
        path = row.get("source_file_id") or row.get("titulo") or ""
        name = row.get("titulo") or Path(path).name
        logical_key = (row.get("document_key") or "").strip()
        if not logical_key:
            continue
        rec = KnownVersion(
            logical_key=logical_key,
            file_hash=row.get("file_hash") or "",
            content_hash=row.get("content_hash"),
            name=name,
            path=path,
            document_id=row.get("id"),
            catalog_id=row.get("catalog_id"),
            version_label=row.get("version_label") or "",
            codigo_documento=extract_codigo_documento(name, path),
            confidence="high",
        )
        if rec.file_hash:
            registry.by_file_hash[rec.file_hash] = rec
        rank = (
            1 if row.get("is_current") else 0,
            1 if row.get("status") == "active" else 0,
            1 if row.get("content_hash") else 0,
        )
        prev = logical_best.get(logical_key)
        if prev is None or rank > prev[0]:
            logical_best[logical_key] = (rank, rec)

    for _, rec in logical_best.values():
        registry.by_logical_key[rec.logical_key] = rec
        registry.by_filename.setdefault(rec.name.lower(), []).append(rec)
    return registry


def scan_manifest(
    manifest_path: Path,
    *,
    extract_root: Path | None = None,
    tenant_slug: str = "monitoring",
    registry: IdentityRegistry | None = None,
    limit: int | None = None,
    simulate: bool = True,
) -> list[VersionDecision]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reg = registry or IdentityRegistry()
    decisions: list[VersionDecision] = []

    for entry in manifest.get("files") or []:
        if limit is not None and len(decisions) >= limit:
            break
        candidate = DocumentCandidate.from_manifest_entry(
            entry,
            tenant_slug=tenant_slug,
            extract_root=extract_root,
        )
        if not candidate:
            continue
        decision = resolve_decision(candidate, reg)
        decisions.append(decision)
        if simulate and decision.index:
            reg.register(
                KnownVersion(
                    logical_key=candidate.logical_key,
                    file_hash=candidate.file_hash,
                    content_hash=candidate.content_hash,
                    name=candidate.name,
                    path=candidate.path,
                    version_label=candidate.version_label,
                    asset_tag=candidate.identity.asset_tag,
                    codigo_documento=candidate.identity.codigo_documento,
                    confidence=candidate.confidence,
                )
            )
    return decisions


def summarize_decisions(decisions: list[VersionDecision]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for d in decisions:
        counts[d.kind] = counts.get(d.kind, 0) + 1
    counts["total"] = len(decisions)
    counts["indexar"] = sum(1 for d in decisions if d.index)
    return counts
