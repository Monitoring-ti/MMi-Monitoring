"""Modelos OCR — capas crudo, normalizado, confianza."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BlockType = Literal["paragraph", "line", "table", "field", "figure", "other"]
ValidationStatus = Literal["pass", "review", "reject"]


@dataclass
class OcrBlock:
    block_index: int
    block_type: BlockType
    text_raw: str
    text_normalized: str = ""
    confidence: float | None = None
    bbox: list[float] | None = None
    language: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_index": self.block_index,
            "block_type": self.block_type,
            "text_raw": self.text_raw,
            "text_normalized": self.text_normalized or self.text_raw,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "language": self.language,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OcrBlock:
        return cls(
            block_index=int(data.get("block_index", 0)),
            block_type=data.get("block_type", "paragraph"),
            text_raw=data.get("text_raw", ""),
            text_normalized=data.get("text_normalized", ""),
            confidence=data.get("confidence"),
            bbox=data.get("bbox"),
            language=data.get("language"),
            extra=dict(data.get("extra") or {}),
        )


@dataclass
class OcrPage:
    page_number: int
    text_raw: str
    text_normalized: str = ""
    confidence: float | None = None
    language: str | None = None
    blocks: list[OcrBlock] = field(default_factory=list)
    page_hash: str = ""
    status: ValidationStatus = "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "text_raw": self.text_raw,
            "text_normalized": self.text_normalized or self.text_raw,
            "confidence": self.confidence,
            "language": self.language,
            "page_hash": self.page_hash,
            "status": self.status,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OcrPage:
        return cls(
            page_number=int(data.get("page_number", 0)),
            text_raw=data.get("text_raw", ""),
            text_normalized=data.get("text_normalized", ""),
            confidence=data.get("confidence"),
            language=data.get("language"),
            page_hash=data.get("page_hash", ""),
            status=data.get("status", "pass"),
            blocks=[OcrBlock.from_dict(b) for b in (data.get("blocks") or [])],
        )


@dataclass
class OcrResult:
    source_path: str
    file_hash: str
    engine: str
    engine_version: str
    model_id: str
    pages: list[OcrPage]
    language: str | None = None
    quality: ValidationStatus = "pass"
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def avg_confidence(self) -> float | None:
        scores = [p.confidence for p in self.pages if p.confidence is not None]
        if not scores:
            return None
        return sum(scores) / len(scores)

    def pages_to_json(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.pages]
