"""Normalización contextual: slides → bloques de texto para chunking RAG."""

from __future__ import annotations

from mmi.index.blocks import Block
from mmi.ingest.pptx_models import PresentationExtract, SlideRecord


def _slide_body_text(slide: SlideRecord) -> str:
    parts: list[str] = []
    for el in slide.elements:
        if el.kind == "title":
            continue
        if el.markdown:
            parts.append(el.markdown)
        elif el.text:
            parts.append(el.text)
        if el.description:
            parts.append(el.description)
    return "\n\n".join(p for p in parts if p.strip())


def _context_header(
    slide: SlideRecord,
    *,
    presentation_name: str,
    version_label: str,
    document_key: str,
    tipo: str,
    modulo: str = "",
) -> str:
    lines = [
        f"Presentación: {presentation_name} | Versión: {version_label}",
    ]
    if slide.section_title:
        lines.append(f"Sección: {slide.section_title}")
    lines.append(f"Diapositiva {slide.slide_number}: {slide.slide_title}")
    meta_parts = [f"clave={document_key}", f"tipo={tipo}"]
    if modulo:
        meta_parts.append(f"módulo={modulo}")
    lines.append(f"Metadatos: {' | '.join(meta_parts)}")
    return "\n".join(lines)


def slide_to_context_text(
    slide: SlideRecord,
    *,
    presentation_name: str,
    version_label: str,
    document_key: str,
    tipo: str = "presentacion",
    modulo: str = "",
    prev_title: str | None = None,
    next_title: str | None = None,
    include_neighbors: bool = False,
) -> str:
    sections: list[str] = [
        _context_header(
            slide,
            presentation_name=presentation_name,
            version_label=version_label,
            document_key=document_key,
            tipo=tipo,
            modulo=modulo,
        ),
        "",
    ]
    if include_neighbors:
        if prev_title:
            sections.append(f"Contexto anterior: {prev_title}")
        if next_title:
            sections.append(f"Contexto posterior: {next_title}")
        if prev_title or next_title:
            sections.append("")

    body = _slide_body_text(slide)
    if body:
        sections.append("Contenido:")
        sections.append(body)

    if slide.speaker_notes:
        sections.append("")
        sections.append("Notas del presentador:")
        sections.append(slide.speaker_notes)

    if slide.visual_summary:
        sections.append("")
        sections.append("Descripción visual:")
        sections.append(slide.visual_summary)

    master = slide.source_location.get("master_context")
    if master:
        sections.append("")
        sections.append(f"Diseño maestro: {master}")

    return "\n".join(sections).strip()


def slides_to_blocks(
    extract: PresentationExtract,
    *,
    document_key: str = "",
    version_label: str = "",
    tipo: str = "presentacion",
    modulo: str = "",
    dense_slide_token_threshold: int = 450,
) -> list[Block]:
    """Convierte slides a bloques; slides densas se parten por elemento."""
    from mmi.index.chunking import count_tokens

    name = extract.source_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    blocks: list[Block] = []
    slides = extract.slides
    titles = [s.slide_title for s in slides]

    for i, slide in enumerate(slides):
        if slide.extraction_quality == "reject":
            continue

        prev_t = titles[i - 1] if i > 0 else None
        next_t = titles[i + 1] if i < len(slides) - 1 else None
        full_text = slide_to_context_text(
            slide,
            presentation_name=name,
            version_label=version_label,
            document_key=document_key,
            tipo=tipo,
            modulo=modulo,
            prev_title=prev_t,
            next_title=next_t,
            include_neighbors=False,
        )
        tk = count_tokens(full_text)

        if tk <= dense_slide_token_threshold or len(slide.elements) <= 1:
            blocks.append(
                Block(
                    text=full_text,
                    slide=slide.slide_number,
                    notes=slide.speaker_notes or None,
                    meta={
                        "slide_title": slide.slide_title,
                        "section_title": slide.section_title,
                        "slide_content_hash": slide.slide_content_hash,
                        "element_kinds": [e.kind for e in slide.elements],
                        "chunk_scope": "slide",
                    },
                )
            )
            continue

        # Slide densa: un bloque por elemento con contexto repetido
        for el in slide.elements:
            if el.kind == "title":
                continue
            el_text = el.markdown or el.text or el.description or ""
            if not el_text.strip():
                continue
            header = _context_header(
                slide,
                presentation_name=name,
                version_label=version_label,
                document_key=document_key,
                tipo=tipo,
                modulo=modulo,
            )
            kind_label = {"table": "Tabla", "chart": "Gráfico", "image": "Imagen"}.get(
                el.kind, "Contenido"
            )
            piece = f"{header}\n\n{kind_label}:\n{el_text}"
            if slide.speaker_notes and el.kind in {"table", "chart"}:
                piece += f"\n\nNotas del presentador:\n{slide.speaker_notes}"
            blocks.append(
                Block(
                    text=piece,
                    slide=slide.slide_number,
                    notes=slide.speaker_notes or None,
                    meta={
                        "slide_title": slide.slide_title,
                        "section_title": slide.section_title,
                        "slide_content_hash": slide.slide_content_hash,
                        "element_kinds": [el.kind],
                        "source_element_orders": [el.order],
                        "chunk_scope": "element",
                    },
                )
            )

    return blocks


def section_aggregate_blocks(
    extract: PresentationExtract,
    *,
    document_key: str = "",
    version_label: str = "",
    tipo: str = "presentacion",
    min_slides_per_section: int = 2,
) -> list[Block]:
    """Fragmentos agrupados por sección para consultas multi-diapositiva."""
    from collections import defaultdict

    by_section: dict[str, list[SlideRecord]] = defaultdict(list)
    for slide in extract.slides:
        if slide.extraction_quality == "reject":
            continue
        key = slide.section_title or "Sin sección"
        by_section[key].append(slide)

    name = extract.source_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    blocks: list[Block] = []
    for section, slides in by_section.items():
        if len(slides) < min_slides_per_section:
            continue
        parts = [
            f"Presentación: {name} | Versión: {version_label}",
            f"Sección: {section}",
            f"Diapositivas: {slides[0].slide_number}–{slides[-1].slide_number}",
            f"Metadatos: clave={document_key} | tipo={tipo}",
            "",
        ]
        for slide in slides:
            body = _slide_body_text(slide)
            if not body and not slide.speaker_notes:
                continue
            parts.append(f"### Diapositiva {slide.slide_number}: {slide.slide_title}")
            if body:
                parts.append(body)
            if slide.speaker_notes:
                parts.append(f"_Notas: {slide.speaker_notes}_")
            parts.append("")

        text = "\n".join(parts).strip()
        if text:
            blocks.append(
                Block(
                    text=text,
                    slide=slides[0].slide_number,
                    meta={
                        "section_title": section,
                        "slide_title": section,
                        "chunk_scope": "section",
                        "slide_range": [slides[0].slide_number, slides[-1].slide_number],
                    },
                )
            )
    return blocks
