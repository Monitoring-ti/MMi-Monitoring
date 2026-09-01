"""Validación OCR — reglas técnicas + catálogo EAM (C4.6)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from mmi.catalog.assets import CatalogAsset, validate_asset_tag
from mmi.config import OcrSettings, get_ocr_settings
from mmi.ingest.ocr_models import OcrBlock, OcrPage, OcrResult, ValidationStatus

_TAG_RE = re.compile(
    r"\b([A-Z]{2,5}-\d{2,5}[A-Z0-9-]*|IFC[- ]?\d{2,5}|SGP-\d+MYC-[A-Z]+-\d+)\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(\d{1,2}[-_/]\d{1,2}[-_/]\d{2,4}|\d{4}[-_/]\d{2}[-_/]\d{2})\b",
)
_UNIT_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(bar|°C|mm|kPa|MPa|RPM|rpm|%)\b", re.IGNORECASE)


@dataclass
class OcrValidation:
    rule: str
    status: ValidationStatus
    field_name: str | None = None
    raw_value: str | None = None
    normalized_value: str | None = None
    expected_value: str | None = None
    confidence: float | None = None
    diff: dict[str, Any] | None = None
    page_number: int | None = None
    block_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_tag(raw: str) -> str:
    return re.sub(r"\s+", "", raw.upper().replace("_", "-"))


def _find_tags(text: str, *, exclude: set[str] | None = None) -> list[str]:
    exclude = {t.upper() for t in (exclude or set())}
    found: list[str] = []
    for match in _TAG_RE.finditer(text or ""):
        tag = _normalize_tag(match.group(1))
        if len(tag) >= 4 and tag not in exclude:
            found.append(tag)
    return sorted(set(found))


def _document_code_excludes(document_key: str | None) -> set[str]:
    if not document_key:
        return set()
    key = _normalize_tag(document_key)
    out = {key}
    if key.startswith("IFC"):
        out.add(key.replace("IFC", "IFC-"))
        out.add(key.replace("IFC-", "IFC"))
    return out


def validate_page_confidence(
    page: OcrPage,
    settings: OcrSettings,
) -> list[OcrValidation]:
    rows: list[OcrValidation] = []
    if page.confidence is None:
        return rows
    if page.confidence < settings.min_page_confidence:
        rows.append(
            OcrValidation(
                rule="page_confidence",
                status="review",
                field_name="page_confidence",
                raw_value=f"{page.confidence:.3f}",
                normalized_value=str(settings.min_page_confidence),
                confidence=page.confidence,
                page_number=page.page_number,
                diff={"threshold": settings.min_page_confidence},
            )
        )
    return rows


def validate_block_confidence(
    page: OcrPage,
    block: OcrBlock,
    settings: OcrSettings,
) -> list[OcrValidation]:
    rows: list[OcrValidation] = []
    if block.confidence is None:
        return rows
    if block.confidence < settings.min_block_confidence:
        rows.append(
            OcrValidation(
                rule="block_confidence",
                status="review",
                field_name="block_confidence",
                raw_value=f"{block.confidence:.3f}",
                normalized_value=str(settings.min_block_confidence),
                confidence=block.confidence,
                page_number=page.page_number,
                block_index=block.block_index,
                diff={"threshold": settings.min_block_confidence},
            )
        )
    return rows


def validate_technical_tags(
    text: str,
    *,
    catalog: dict[str, CatalogAsset] | None,
    settings: OcrSettings,
    page_number: int | None = None,
    block_index: int | None = None,
    confidence: float | None = None,
    exclude_tags: set[str] | None = None,
) -> list[OcrValidation]:
    rows: list[OcrValidation] = []
    for tag in _find_tags(text, exclude=exclude_tags):
        in_catalog = validate_asset_tag(tag, catalog)
        status: ValidationStatus = "pass"
        if not in_catalog:
            status = "review"
        if confidence is not None and confidence < settings.critical_field_confidence:
            status = "review"
        rows.append(
            OcrValidation(
                rule="technical_tag",
                status=status,
                field_name="asset_tag",
                raw_value=tag,
                normalized_value=tag if in_catalog else None,
                expected_value=tag if in_catalog else None,
                confidence=confidence,
                page_number=page_number,
                block_index=block_index,
                diff={"catalog_match": in_catalog},
            )
        )
    return rows


def validate_dates_and_units(
    text: str,
    *,
    page_number: int | None = None,
    block_index: int | None = None,
    confidence: float | None = None,
    settings: OcrSettings | None = None,
) -> list[OcrValidation]:
    settings = settings or get_ocr_settings()
    rows: list[OcrValidation] = []
    for match in _DATE_RE.finditer(text or ""):
        conf = confidence
        status: ValidationStatus = "pass"
        if conf is not None and conf < settings.critical_field_confidence:
            status = "review"
        rows.append(
            OcrValidation(
                rule="date_field",
                status=status,
                field_name="date",
                raw_value=match.group(1),
                confidence=conf,
                page_number=page_number,
                block_index=block_index,
            )
        )
    for match in _UNIT_RE.finditer(text or ""):
        conf = confidence
        status = "pass"
        if conf is not None and conf < settings.critical_field_confidence:
            status = "review"
        rows.append(
            OcrValidation(
                rule="unit_field",
                status=status,
                field_name="unit",
                raw_value=match.group(0),
                normalized_value=f"{match.group(1)} {match.group(2)}",
                confidence=conf,
                page_number=page_number,
                block_index=block_index,
            )
        )
    return rows


def validate_ocr_result(
    ocr: OcrResult,
    *,
    catalog: dict[str, CatalogAsset] | None = None,
    settings: OcrSettings | None = None,
    document_key: str | None = None,
) -> tuple[list[OcrValidation], ValidationStatus]:
    """Ejecuta reglas C4 sobre páginas y bloques."""
    settings = settings or get_ocr_settings()
    validations: list[OcrValidation] = []
    exclude_tags = _document_code_excludes(document_key)

    for page in ocr.pages:
        validations.extend(validate_page_confidence(page, settings))
        page_text = page.text_raw or ""
        validations.extend(
            validate_technical_tags(
                page_text,
                catalog=catalog,
                settings=settings,
                page_number=page.page_number,
                confidence=page.confidence,
                exclude_tags=exclude_tags,
            )
        )
        validations.extend(
            validate_dates_and_units(
                page_text,
                page_number=page.page_number,
                confidence=page.confidence,
                settings=settings,
            )
        )
        for block in page.blocks:
            validations.extend(validate_block_confidence(page, block, settings))
            text = block.text_raw or ""
            validations.extend(
                validate_technical_tags(
                    text,
                    catalog=catalog,
                    settings=settings,
                    page_number=page.page_number,
                    block_index=block.block_index,
                    confidence=block.confidence,
                    exclude_tags=exclude_tags,
                )
            )
            if block.text_raw != block.text_normalized:
                validations.append(
                    OcrValidation(
                        rule="raw_normalized_diff",
                        status="pass",
                        field_name="text",
                        raw_value=(block.text_raw or "")[:200],
                        normalized_value=(block.text_normalized or "")[:200],
                        confidence=block.confidence,
                        page_number=page.page_number,
                        block_index=block.block_index,
                        diff={
                            "raw": block.text_raw,
                            "normalized": block.text_normalized,
                        },
                    )
                )

    if any(v.status == "reject" for v in validations):
        quality: ValidationStatus = "reject"
    elif any(v.status == "review" for v in validations):
        quality = "review"
    elif ocr.quality == "review":
        quality = "review"
    else:
        quality = "pass"
    return validations, quality


def validations_summary(validations: list[OcrValidation]) -> dict[str, int]:
    summary = {"pass": 0, "review": 0, "reject": 0}
    for row in validations:
        summary[row.status] = summary.get(row.status, 0) + 1
    return summary
