# Fase 3 — Validación del motor híbrido

Fecha: 2026-08-29. Motor: `pipeline/search.py` (HybridSearchEngine).

## Diseño del motor

Pipeline de consulta en tres pasos:

1. **Retrieval híbrido en Qdrant**: prefetch denso (OpenAI `text-embedding-3-small`, 1536 dims) + disperso (BM25 vía fastembed), fusión **RRF**, filtro obligatorio por `tenant_id` + `is_current`.
2. **Boost por criticidad**: los chunks `criticality_level=seguridad` reciben un factor **1.5×** cuando la consulta es de índole operativa/seguridad (detectada por regex de palabras clave). Boost leve **1.1×** a la versión vigente.
3. **Reranking**: reordenamiento por score ajustado (RRF + boosts), con **deduplicación por (document_id, section_path)** y enriquecimiento con `titulo`/`version_label` desde Postgres.

## Resultados de la validación (6 consultas sobre el corpus completo)

| Consulta | Tipo | Top-1 | ¿Boost seguridad funcionó? |
|---|---|---|---|
| ¿Qué es la mantenibilidad…? | definición | presentacion (Confiabilidad) | n/a |
| modos de falla y criticidad FMECA | metodología | presentacion (Taller FMECA) | n/a |
| advertencia seguridad bloqueo antes de operar | seguridad | **otro (Señalética) *SEG*** | **Sí: 3/4 chunks de seguridad en top-4** |
| criterios de criticidad NCC-30 | norma | otro (criticidad) *SEG* | n/a |
| check list mantenibilidad accesibilidad | tabla | guia (Rev 4) | n/a |
| ¿Qué es el RCM vs FMECA? | metodología | guia (Desarrollo FMECA, Rev 6) *SEG* | n/a |

## Observaciones

- El **boost de seguridad funciona**: en la consulta de seguridad, 3 de los 4 primeros resultados son chunks etiquetados `seguridad`, y el top-1 es un chunk de señalética/advertencia con score elevado (1.65 tras el boost).
- El **reranking deduplica** por documento/sección: no hay dos chunks del mismo documento y sección en el top-4.
- El enriquecimiento añade `section_path` (p.ej. `8.6 ANÁLISIS DE LOS MODOS DE FALLA`) y `version_label` (Rev 4/5/6), lo que habilita citas precisas en la Fase 4.
- La recuperación es relevante en las 6 consultas: cada una devuelve el documento/sección correcta del dominio.

## Parámetros del motor

| Parámetro | Valor |
|---|---|
| Fusión | RRF (dense + sparse) |
| Prefetch limit | 20 por rama |
| Boost seguridad | 1.5× (solo en consultas de seguridad) |
| Boost versión vigente | 1.1× |
| Deduplicación | por (document_id, section_path) |
| Filtro obligatorio | tenant_id + is_current |
