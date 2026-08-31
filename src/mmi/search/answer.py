"""Respuesta RAG con citas vía OpenRouter."""

from __future__ import annotations

import re
from dataclasses import dataclass

from mmi.llm.openrouter import chat_completion
from mmi.search.engine import HybridSearchEngine, SearchResult

CITE_RE = re.compile(r"\[(\d+)\]")

SYSTEM_PROMPT = """Eres un asistente de memoria técnica industrial (mantenibilidad, confiabilidad, NCC-30).
Responde SOLO con la información de las evidencias numeradas [1], [2], etc.

Estructura obligatoria (usa estos títulos en markdown):
## Resumen
1-2 oraciones que respondan directamente la consulta, con citas [n].

## Detalle
- Viñetas o párrafos cortos; cada afirmación relevante debe llevar al menos una cita [n].
- Ordena las ideas de lo general a lo específico.
- Usa solo evidencias que aporten a la pregunta; no cites por citar.

Reglas:
- Cita con el número exacto de la evidencia: [1], [2], etc.
- Si no hay información suficiente, dilo en Resumen y no inventes datos.
- Responde en español, claro y conciso.
- No incluyas sección de bibliografía ni lista de referencias al final (se muestra aparte).
- No inventes normas, revisiones ni datos que no aparezcan en las evidencias."""


@dataclass
class AnswerResult:
    query: str
    answer: str
    model: str
    sources: list[dict]
    references: list[dict]
    cited_indices: list[int]
    evidence_count: int
    hits: list[SearchResult]


def extract_cited_indices(text: str) -> list[int]:
    seen: set[int] = set()
    order: list[int] = []
    for match in CITE_RE.finditer(text):
        idx = int(match.group(1))
        if idx not in seen:
            seen.add(idx)
            order.append(idx)
    return order


def build_references(answer: str, hits: list[SearchResult]) -> tuple[list[int], list[dict]]:
    cited = extract_cited_indices(answer)
    references: list[dict] = []
    for idx in cited:
        if not (1 <= idx <= len(hits)):
            continue
        hit = hits[idx - 1]
        references.append(
            {
                "index": idx,
                "citation": hit.citation,
                "titulo": hit.titulo,
                "tipo": hit.tipo,
                "version_label": hit.version_label,
                "section_path": hit.section_path,
                "page_start": hit.page_start,
                "page_end": hit.page_end,
                "score": round(hit.score, 4),
                "snippet": hit.content[:280].strip(),
            }
        )
    return cited, references


def _format_evidence(hits: list[SearchResult]) -> str:
    blocks: list[str] = []
    for i, h in enumerate(hits, 1):
        cite = h.citation or h.titulo or f"Fuente {i}"
        blocks.append(f"[{i}] {cite}\n{h.content[:3500]}")
    return "\n\n".join(blocks)


def generate_answer(query: str, hits: list[SearchResult], model: str | None = None) -> AnswerResult:
    import os

    if not hits:
        return AnswerResult(
            query=query,
            answer="No encontré evidencia en el corpus para responder esta consulta.",
            model=model or os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            sources=[],
            references=[],
            cited_indices=[],
            evidence_count=0,
            hits=[],
        )

    evidence = _format_evidence(hits)
    user_prompt = f"""Consulta del usuario:
{query}

Evidencias:
{evidence}

Redacta la respuesta con las secciones ## Resumen y ## Detalle, citando [1], [2], etc."""

    used_model = model or os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    answer = chat_completion(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model=used_model,
    )

    sources = [
        {
            "index": i,
            "citation": h.citation,
            "titulo": h.titulo,
            "tipo": h.tipo,
            "version_label": h.version_label,
            "section_path": h.section_path,
            "page_start": h.page_start,
            "page_end": h.page_end,
            "score": round(h.score, 4),
        }
        for i, h in enumerate(hits, 1)
    ]
    cited_indices, references = build_references(answer, hits)

    return AnswerResult(
        query=query,
        answer=answer,
        model=used_model,
        sources=sources,
        references=references,
        cited_indices=cited_indices,
        evidence_count=len(hits),
        hits=hits,
    )


def ask(
    query: str,
    engine: HybridSearchEngine,
    *,
    limit: int = 6,
    model: str | None = None,
) -> AnswerResult:
    hits = engine.search(query, limit=limit)
    return generate_answer(query, hits, model=model)
