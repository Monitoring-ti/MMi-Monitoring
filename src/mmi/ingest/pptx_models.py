"""Modelos para extracción jerárquica PPTX (presentación → slide → elemento)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SlideQuality = Literal["pass", "review", "reject"]
ElementKind = Literal[
    "text_box",
    "title",
    "table",
    "chart",
    "image",
    "smartart",
    "other",
]


@dataclass
class SlideElement:
    kind: ElementKind
    order: int
    text: str = ""
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    markdown: str = ""
    chart_title: str | None = None
    axes: dict[str, str] = field(default_factory=dict)
    legend: list[str] = field(default_factory=list)
    series: list[dict[str, Any]] = field(default_factory=list)
    media_ref: str | None = None
    description: str | None = None
    needs_visual_analysis: bool = False
    bbox: list[int] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "order": self.order}
        if self.text:
            out["text"] = self.text
        if self.headers:
            out["headers"] = self.headers
        if self.rows:
            out["rows"] = self.rows
        if self.markdown:
            out["markdown"] = self.markdown
        if self.chart_title:
            out["chart_title"] = self.chart_title
        if self.axes:
            out["axes"] = self.axes
        if self.legend:
            out["legend"] = self.legend
        if self.series:
            out["series"] = self.series
        if self.media_ref:
            out["media_ref"] = self.media_ref
        if self.description:
            out["description"] = self.description
        if self.needs_visual_analysis:
            out["needs_visual_analysis"] = True
        if self.bbox:
            out["bbox"] = self.bbox
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlideElement:
        return cls(
            kind=data.get("kind", "other"),
            order=int(data.get("order", 0)),
            text=data.get("text", ""),
            headers=list(data.get("headers") or []),
            rows=[list(r) for r in (data.get("rows") or [])],
            markdown=data.get("markdown", ""),
            chart_title=data.get("chart_title"),
            axes=dict(data.get("axes") or {}),
            legend=list(data.get("legend") or []),
            series=list(data.get("series") or []),
            media_ref=data.get("media_ref"),
            description=data.get("description"),
            needs_visual_analysis=bool(data.get("needs_visual_analysis")),
            bbox=data.get("bbox"),
        )


@dataclass
class SlideRecord:
    presentation_id: str | None
    version_id: str | None
    slide_number: int
    slide_title: str
    section_title: str
    elements: list[SlideElement] = field(default_factory=list)
    speaker_notes: str = ""
    visual_summary: str = ""
    source_location: dict[str, Any] = field(default_factory=dict)
    slide_content_hash: str = ""
    extraction_quality: SlideQuality = "reject"

    def to_dict(self) -> dict[str, Any]:
        return {
            "presentation_id": self.presentation_id,
            "version_id": self.version_id,
            "slide_number": self.slide_number,
            "slide_title": self.slide_title,
            "section_title": self.section_title,
            "elements": [e.to_dict() for e in self.elements],
            "speaker_notes": self.speaker_notes,
            "visual_summary": self.visual_summary,
            "source_location": self.source_location,
            "slide_content_hash": self.slide_content_hash,
            "extraction_quality": self.extraction_quality,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlideRecord:
        return cls(
            presentation_id=data.get("presentation_id"),
            version_id=data.get("version_id"),
            slide_number=int(data.get("slide_number", 0)),
            slide_title=data.get("slide_title", ""),
            section_title=data.get("section_title", ""),
            elements=[SlideElement.from_dict(e) for e in (data.get("elements") or [])],
            speaker_notes=data.get("speaker_notes", ""),
            visual_summary=data.get("visual_summary", ""),
            source_location=dict(data.get("source_location") or {}),
            slide_content_hash=data.get("slide_content_hash", ""),
            extraction_quality=data.get("extraction_quality", "reject"),
        )


@dataclass
class PresentationExtract:
    source_path: str
    file_hash: str
    slides: list[SlideRecord]
    quality: SlideQuality
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def slide_count(self) -> int:
        return len(self.slides)

    @property
    def slides_pass(self) -> int:
        return sum(1 for s in self.slides if s.extraction_quality == "pass")

    def slides_to_json(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.slides]
