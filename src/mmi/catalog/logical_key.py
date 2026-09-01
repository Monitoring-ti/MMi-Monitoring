"""Construcción de logical_key (document_key de negocio)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

_CODE_RE = re.compile(
    r"\b([A-Z]{2,5}-\d{2}[A-Z0-9]{0,4}-[A-Z0-9-]{4,}|SGP-\d+MYC-[A-Z]+-\d+|NCC-\d+|IFC-\d+)\b",
    re.IGNORECASE,
)
_GUIDE_NUM_RE = re.compile(r"\b(GUIGS|GUIG|PROGS|SOP)[-_ ]?(\d+)\b", re.IGNORECASE)
_REV_RE = re.compile(r"\b(rev\.?\s*[a-z0-9]+|revision\s*[a-z0-9]+)\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(20\d{2}[-_/]?\d{2}[-_/]?\d{2}|\d{2}[-_/]\d{2}[-_/]20\d{2})\b")
_ASSET_RE = re.compile(
    r"\b([A-Z]{1,4}[-_ ]?\d{1,3}[-_ ]?[A-Z]{0,3}[-_ ]?\d{0,3})\b",
)
_MODULO_TOKENS = (
    "DCH",
    "MYC",
    "ENF",
    "MRI",
    "MSO",
    "SPCI",
    "DRT",
    "GPRO",
    "M&C",
    "MC",
    "ELECTRICO",
    "MECANICO",
)
_VENDOR_TOKENS = (
    "siemens",
    "schneider",
    "abb",
    "honeywell",
    "emerson",
    "rockwell",
    "ge",
    "metso",
    "flsmidth",
)


def normalize_key_part(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(name: str) -> str:
    stem = Path(name).stem
    text = _REV_RE.sub(" ", stem)
    text = _DATE_RE.sub(" ", text)
    text = re.sub(r"[_\-]+", " ", text)
    return normalize_key_part(text)


def extract_codigo_documento(name: str, relative_path: str = "") -> str:
    for source in (name, relative_path):
        m = _CODE_RE.search(source or "")
        if m:
            return m.group(1).upper()
    return ""


def extract_numero_guia(name: str, relative_path: str = "") -> str:
    for source in (name, relative_path):
        m = _GUIDE_NUM_RE.search(source or "")
        if m:
            return f"{m.group(1).upper()}-{m.group(2)}"
    return ""


def extract_modulo(name: str, relative_path: str = "") -> str:
    combined = f"{relative_path} {name}".upper()
    for token in _MODULO_TOKENS:
        if token.replace("&", "") in combined.replace("&", ""):
            return token.replace("&", "")
    parts = re.split(r"[\\/]", relative_path or "")
    for part in parts:
        norm = normalize_key_part(part)
        if norm in {"entregables", "anexos", "check list", "guia", "norma"}:
            continue
        if len(norm) >= 3:
            return norm[:40]
    return ""


def extract_asset_tag(name: str, relative_path: str = "") -> str:
    combined = f"{relative_path} {name}"
    best = ""
    for m in _ASSET_RE.finditer(combined.upper()):
        candidate = m.group(1).replace(" ", "-").replace("_", "-")
        if len(candidate) >= 4 and not candidate.startswith("REV"):
            if len(candidate) > len(best):
                best = candidate
    return best


def extract_proveedor(name: str, relative_path: str = "") -> str:
    combined = f"{relative_path} {name}".lower()
    for vendor in _VENDOR_TOKENS:
        if vendor in combined:
            return vendor
    return ""


@dataclass
class DocumentIdentityMeta:
    tenant_slug: str = "monitoring"
    origen: str = "ods1"
    name: str = ""
    relative_path: str = ""
    tipo_documental: str = "otro"
    asset_tag: str = ""
    modulo: str = ""
    codigo_documento: str = ""
    numero_guia: str = ""
    titulo_normalizado: str = ""
    proveedor: str = ""
    fabricante: str = ""
    modelo: str = ""
    document_key_hint: str = ""
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_manifest_entry(
        cls,
        entry: dict,
        *,
        tenant_slug: str = "monitoring",
    ) -> DocumentIdentityMeta:
        name = entry.get("name") or Path(entry.get("absolute_path") or "").name
        rel = entry.get("relative_path") or ""
        meta = cls(
            tenant_slug=tenant_slug,
            origen=(entry.get("source") or "ods1").lower(),
            name=name,
            relative_path=rel,
            tipo_documental=(entry.get("suggested_tipo") or entry.get("tipo") or "otro").lower(),
            document_key_hint=(entry.get("document_key") or "").strip(),
            asset_tag=(entry.get("asset_tag") or "").strip(),
            modulo=(entry.get("modulo") or entry.get("module") or "").strip(),
            codigo_documento=(entry.get("codigo_documento") or "").strip(),
            numero_guia=(entry.get("numero_guia") or "").strip(),
            fabricante=(entry.get("fabricante") or entry.get("manufacturer") or "").strip(),
            modelo=(entry.get("modelo") or entry.get("model") or "").strip(),
        )
        if not meta.codigo_documento:
            meta.codigo_documento = extract_codigo_documento(name, rel)
        if not meta.numero_guia:
            meta.numero_guia = extract_numero_guia(name, rel)
        if not meta.modulo:
            meta.modulo = extract_modulo(name, rel)
        if not meta.asset_tag:
            meta.asset_tag = extract_asset_tag(name, rel)
        if not meta.proveedor:
            meta.proveedor = extract_proveedor(name, rel)
        meta.titulo_normalizado = normalize_title(name)
        return meta


def derive_logical_key(meta: DocumentIdentityMeta) -> str:
    """Devuelve document_key estable (logical_key) según spec R5."""
    if meta.document_key_hint:
        return meta.document_key_hint

    tenant = normalize_key_part(meta.tenant_slug)
    origen = normalize_key_part(meta.origen) or "ods1"
    tipo = normalize_key_part(meta.tipo_documental) or "otro"
    modulo = normalize_key_part(meta.modulo)
    asset = normalize_key_part(meta.asset_tag)
    codigo = normalize_key_part(meta.codigo_documento)

    if codigo:
        parts = [tenant, origen, codigo, asset, tipo, modulo]
        return "|".join(p for p in parts if p)

    titulo = normalize_key_part(meta.titulo_normalizado or meta.name)
    fabricante = normalize_key_part(meta.fabricante or meta.proveedor)
    modelo = normalize_key_part(meta.modelo)
    guia = normalize_key_part(meta.numero_guia)
    if guia:
        parts = [tenant, origen, guia, asset, tipo, modulo]
        key = "|".join(p for p in parts if p)
        if key.count("|") >= 2:
            return key

    parts = [tenant, titulo, asset, fabricante, modelo, modulo]
    key = "|".join(p for p in parts if p)
    return key or normalize_key_part(Path(meta.name).stem) or "unknown"


def identity_confidence(meta: DocumentIdentityMeta, logical_key: str) -> str:
    """high | medium | low — para R4."""
    if meta.document_key_hint or meta.codigo_documento:
        return "high"
    if meta.numero_guia and meta.asset_tag:
        return "high"
    if meta.codigo_documento or (meta.numero_guia and meta.modulo):
        return "medium"
    if logical_key.count("|") >= 3:
        return "medium"
    return "low"
