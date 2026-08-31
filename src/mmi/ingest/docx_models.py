"""Modelos para extracción jerárquica DOC/DOCX."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BlockQuality = Literal["pass", "review", "reject"]
BlockType = Literal[
    "heading",
    "paragraph",
    "list",
    "table",
    "image",
    "footnote",
    "reference",
    "comment",
    "other",
]


@dataclass
class DocBlock:
    block_index: int
    block_type: BlockType
    text_raw: str
    text_normalized: str = ""
    level: int | None = None
    section_path: str = ""
    page_or_position: int | None = None
    block_content_hash: str = ""
    extraction_quality: BlockQuality = "pass"
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    markdown: str = ""
    media_ref: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_index": self.block_index,
            "block_type": self.block_type,
            "text_raw": self.text_raw,
            "text_normalized": self.text_normalized or self.text_raw,
            "level": self.level,
            "section_path": self.section_path,
            "page_or_position": self.page_or_position,
            "block_content_hash": self.block_content_hash,
            "extraction_quality": self.extraction_quality,
            "headers": self.headers,
            "rows": self.rows,
            "markdown": self.markdown,
            "media_ref": self.media_ref,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocBlock:
        return cls(
            block_index=int(data.get("block_index", 0)),
            block_type=data.get("block_type", "paragraph"),
            text_raw=data.get("text_raw", ""),
            text_normalized=data.get("text_normalized", ""),
            level=data.get("level"),
            section_path=data.get("section_path", ""),
            page_or_position=data.get("page_or_position"),
            block_content_hash=data.get("block_content_hash", ""),
            extraction_quality=data.get("extraction_quality", "pass"),
            headers=list(data.get("headers") or []),
            rows=[list(r) for r in (data.get("rows") or [])],
            markdown=data.get("markdown", ""),
            media_ref=data.get("media_ref"),
            extra=dict(data.get("extra") or {}),
        )


@dataclass
class DocumentExtract:
    source_path: str
    file_hash: str
    blocks: list[DocBlock]
    quality: BlockQuality
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def block_count(self) -> int:
        return len(self.blocks)

    @property
    def blocks_pass(self) -> int:
        return sum(1 for b in self.blocks if b.extraction_quality == "pass")

    def blocks_to_json(self) -> list[dict[str, Any]]:
        return [b.to_dict() for b in self.blocks]
