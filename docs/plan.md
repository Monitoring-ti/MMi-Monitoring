# MMi by Monitoring — Plan de implementación

**Producto:** memoria técnica industrial (buscar y citar documentos).  
**Recorte MVP:** RAG documental sobre corpus NCC30/ODS1 · Motor MMI ✅ ([`plan-mmi-motor.md`](plan-mmi-motor.md)). Sin agentes autónomos ni n8n.  
**Repo:** [Monitoring-ti/MMi-Monitoring](https://github.com/Monitoring-ti/MMi-Monitoring)  
**Última actualización:** 2026-09-01 · rama `analisis-datos`

**Fuentes de verdad (métricas):** regenerar antes de citar números.

| Artefacto | Uso |
|-----------|-----|
| `out/analysis-status.json` | Fase 0 (`pass` / `review` / `reject`), indexación por archivo |
| `out/index-corpus-summary.json` | Resumen batch de `index_corpus` (complementario) |
| `out/data-analysis/report.json` | Agregados Fase D (`data_report`) |

```powershell
.venv\Scripts\python -m mmi.tools.analysis_status --skip-reviews
.venv\Scripts\python -m mmi.tools.data_report
```

---

## 1. Objetivo y criterios de aceptación

### Objetivos medibles

1. **Buscar y citar evidencia trazable** — fragmentos con documento, versión y página/sección.
2. **Responder consultas con control de fuentes y conflictos** — respuesta estructurada con citas `[1]`, `[2]`; banner si hay versiones contradictorias (C2).
3. **Revisar y aprobar documentos antes de indexarlos** — Fase 0 con estados `pass` / `review` / `reject`; nada en `reject` entra al índice activo.

### Criterios de aceptación del MVP

| Criterio | Regla |
|----------|-------|
| Versiones activas | Solo `status=active` / `is_current=true` en búsqueda tras `reindex_clean` |
| Citas obligatorias | Toda respuesta RAG incluye referencias verificables |
| Filtro por activo | Búsqueda y Motor aceptan `asset_codes`; Mapa filtra por activo |
| Cero indexación de `reject` | `status=reject` en Fase 0 → `indexable=false` |
| Activación atómica | Versión no visible hasta que todos los chunks estén en PG + Qdrant |
| Trazabilidad | No inventar normas, revisiones ni códigos EAM |

### Fuera de alcance MVP

Auth multi-tenant · despliegue cloud · cola Redis (C5) · rotación de claves (operación, no bloqueante de demo local).

---

## 2. Estado real

*Valores de referencia al 2026-09-01. Verificar con `analysis-status.json` → `summary`.*

### Métricas actuales

| Métrica | Valor | Campo / nota |
|---------|-------|----------------|
| Manifest ODS1 | 1582 | `summary.total` |
| Fase 0 pass | 1435 | `summary.pass` |
| Fase 0 review | 1 | `summary.review` |
| Fase 0 reject | **46** | `summary.reject` — no mezclar con excluidos |
| Excluidos análisis | 100 | `summary.excluidos` |
| Indexados (activos) | **1274** | `summary.indexados` — estado `active` / `indexed` |
| Duplicados índice | 250 | `summary.index_duplicados` |
| Pass sin indexar activo | ~161 | `pass` − `indexados` (duplicados + pendientes) |
| Err. índice pendientes | 0 | `summary.index_pendientes` + `index_errores` |
| Validación RAG | 10/10 | `out/rag-validation.json` |
| Smoke consultas | 3/3 | `out/query-smoke.json` |
| Golden set | 35/35 recall@5 · MRR ~0.91 | `out/golden-set-eval.json` |
| Planos INF TEC | 50 / 309 PDFs | `out/plan-scan.json` |

> **Inconsistencias corregidas:** `46` reject + `1` review (no cuentan excluidos). `1274` indexados desde `summary.indexados` (no `1096`, cifra del batch en `index_summary`). Regenerar siempre con `analysis_status` antes de citar.

### Pendientes reales

| # | Ítem | Depende de |
|---|------|------------|
| 1 | Reindexación limpia — solo Rev vigente en búsqueda | `reindex_clean` |
| 2 | Batch OCR — 50 planos INF TEC | Azure + `ocr_worker` |
| 3 | Persistencia `ocr_*` en Supabase | `003_ocr_schema.sql` |
| 4 | PPTX visual → OCR por región | C4.14 |
| 5 | Filtros UI búsqueda (tipo, dominio, criticidad) | — |
| 6 | Golden set en CI (C3.3) | `eval_retrieval` en PR |
| 7 | Prueba de carga documentada | `load_test` |
| 8 | Co-ocurrencia activo×doc en grafo (D1) | PG + `data_report` |
| 9 | Soporte `.xlsm` (~119 archivos) | prioridad baja |

### Riesgos bloqueantes

| Riesgo | Impacto | Acción preventiva |
|--------|---------|-------------------|
| Versiones antiguas en índice | Respuestas con Rev obsoleta | Ejecutar `reindex_clean`; validar conteos antes/después |
| Servidor incorrecto en :8773 | 404 en `/api/ask` | Health check: `GET /api/graph/health` o `serve_local --port 8773` |
| HTML vía `file://` | APIs no disponibles | Siempre `serve_local` para UI con backend |
| Claves expuestas | Compromiso de cuentas | Rotar en proveedores; no commitear `.env` |
| OCR baja confianza | Tags EAM erróneos | Umbral confianza + revisión campos críticos; no activar versión |
| Fallos parciales indexación | Chunks huérfanos | `--resume` / `--retry-errors` por etapa |
| Conflictos documentales | Respuesta incorrecta | C2 bloquea banner; validación humana antes de confiar |

### Resumen ejecutivo (5 líneas)

- **Cerrado:** Fase 0 masiva · 1274 indexados · búsqueda híbrida · RAG · Motor MMI · Mapa E1–E4 · Fase D dashboard.
- **En curso:** calidad índice (reindex limpio) · escala OCR · enriquecimiento grafo (D1).
- **Siguiente:** `reindex_clean` → batch planos → `003_ocr_schema.sql`.
- **Bloqueado:** nada crítico; demo local operativa con `serve_local`.
- **Validación:** lote 1 en [`plan-anexo-operaciones.md`](plan-anexo-operaciones.md#lote-1-validación).

---

## 3. Arquitectura y reglas de datos

### Flujo por estados

```
recepción → identificación → extracción → QA → aprobación → indexación → activación → consulta
```

| Etapa | Herramienta / módulo | Salida |
|-------|---------------------|--------|
| Recepción | `corpus_picker`, manifest | archivo + `included_in_analysis` |
| Identificación | `file_hash`, `logical_key`, `version_id` | decisión R1–R4 |
| Extracción | `process_manifest` → `out/ods1-extract/` | texto persistido **antes** de embeddings |
| QA | `analysis_status`, `review.html` | `pass` / `review` / `reject` |
| Aprobación | operador en dashboard | solo `pass` → `indexable` |
| Indexación | `index_corpus` → PG + Qdrant | chunks + vectores |
| Activación | `pg_activate_document_version` | atómica tras todos los chunks |
| Consulta | `search.html` · `rag.html` · `motor.html` · `mapa.html` | `serve_local :8773` |

### Identificadores

| Campo | Rol |
|-------|-----|
| `file_hash` | Huella SHA-256 del archivo (bytes) |
| `content_hash` | Huella del texto extraído normalizado |
| `logical_key` / `document_key` | Identidad de negocio del documento |
| `version_id` | Fila en `documents` + `version_label` |

### Estados del documento

| Estado | Fase | Indexable |
|--------|------|-----------|
| `processing` | En pipeline | No |
| `pass` | Fase 0 OK | Sí |
| `review` | QA dudoso | No hasta resolver |
| `reject` | Calidad insuficiente | **Nunca** |
| `active` | Versión vigente en índice | Sí (visible en búsqueda) |
| `superseded` | Versión anterior | No (histórico) |

### Reglas de identidad (decisiones cerradas)

| Condición | Acción |
|-----------|--------|
| `file_hash` igual | Duplicado exacto → `skipped_exact_duplicate`; no re-indexar |
| `logical_key` igual, `content_hash` distinto | Nueva versión → indexar → activar; anterior `superseded` |
| `logical_key` distinto | Documento separado aunque el nombre de archivo coincida |
| Identidad dudosa | `needs_review` → no fusionar ni activar automáticamente |

**Quién cambia la versión activa:** operador con acceso a `review.html` / `ingestion-action` tras validar Fase 0.  
**Revertir activación:** marcar versión como `superseded` en PG + Qdrant (`pg_activate_document_version` con versión anterior); no borrar chunks sin `reindex_clean`.

### Stack técnico

| Capa | Decisión |
|------|----------|
| Vectores | Qdrant Cloud |
| Metadatos | Supabase (Postgres REST) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Generación | OpenRouter (`openai/gpt-4o-mini`) |
| OCR | Azure Document Intelligence |
| Integración | APIs Python directas, sin n8n |

**Variables** (`.env`, gitignored): `SUPABASE_*`, `QDRANT_*`, `OPENAI_API_KEY`, `OPENROUTER_*`, `AZURE_DOCUMENT_INTELLIGENCE_*`.

Detalle identidad: [`plan-document-identity.md`](plan-document-identity.md).

---

## 4. Backlog priorizado

| # | Ítem | Responsable | Criterio de done | Dependencia |
|---|------|-------------|------------------|-------------|
| 1 | **Reindexación limpia** Rev vigente | Dev | `reindex_clean` ejecutado; búsqueda sin hits Rev antigua; conteos validados | Índice actual estable |
| 2 | **Escala OCR** 50 planos + persistencia PG | Dev | ≥10 planos indexados; `ocr_*` en Supabase | `003_ocr_schema.sql` · Azure |
| 3 | **PPTX visual** OCR por región | Dev | Diapos solo gráfico extraídas en piloto | C4 núcleo ✅ |
| 4 | **Calidad** — golden CI + revisión humana OCR | Dev + QA | `eval_retrieval` en PR; campos críticos revisados | Golden set C3 |
| 5 | **Prueba de carga** documentada | Dev | `load_test` con reporte en `out/` y umbral latencia | `serve_local` |
| 6 | **Filtros UI** búsqueda | Dev | Filtro tipo/dominio/criticidad en `search.html` | — |
| 7 | **Co-ocurrencia D1** en grafo | Dev | Aristas `co_occurs` desde PG en `/api/graph/expand` | Fase D parcial ✅ |
| 8 | **XLSM** (~119 archivos) | Dev | Extractor o guía conversión documentada | Prioridad baja |

### Comandos críticos

**Precondiciones:** `cd mmi-by-monitoring` · venv activo (`.venv\Scripts\activate`) · `.env` configurado · para UI con API usar `serve_local` (no abrir HTML por `file://`).

```powershell
# Extraer (Fase 0)
.venv\Scripts\python -m mmi.tools.process_manifest

# Revisar QA
.venv\Scripts\python -m mmi.tools.analysis_status --skip-reviews
# → out/review.html vía serve_local

# Indexar
.venv\Scripts\python -m mmi.tools.index_corpus --resume

# Reanudar fallos
.venv\Scripts\python -m mmi.tools.index_corpus --retry-errors

# Reindexar solo versiones vigentes
.venv\Scripts\python -m mmi.tools.reindex_clean --dry-run
.venv\Scripts\python -m mmi.tools.reindex_clean --reindex

# Validación RAG
.venv\Scripts\python -m mmi.tools.validate_rag --search-only
.venv\Scripts\python -m mmi.tools.query_smoke

# Servidor (obligatorio para UI + APIs)
.venv\Scripts\python -m mmi.tools.serve_local --port 8773
```

Comandos extendidos, URLs y lote 1: [`plan-anexo-operaciones.md`](plan-anexo-operaciones.md).

---

## Anexos y referencias

| Documento | Tipo | Descripción |
|-----------|------|-------------|
| [`plan-anexo-operaciones.md`](plan-anexo-operaciones.md) | Operación | Comandos completos, URLs locales, lote 1 validación |
| [`plan-fase-c.md`](plan-fase-c.md) | Especificación | Reranker, golden set, conflictos, cierre consultas |
| [`plan-fase-c-ocr.md`](plan-fase-c-ocr.md) | Especificación | OCR con incertidumbre y gates de activación |
| [`plan-analisis-datos.md`](plan-analisis-datos.md) | Especificación | Fase D: cobertura, planos, calidad |
| [`plan-mapa-conocimiento.md`](plan-mapa-conocimiento.md) | Especificación | Fase E: grafo `mapa.html` |
| [`plan-mmi-motor.md`](plan-mmi-motor.md) | Especificación | Motor activo + síntoma |
| [`plan-document-identity.md`](plan-document-identity.md) | Especificación | Reglas `file_hash` · `logical_key` · versión |
| [`migrations/003_ocr_schema.sql`](migrations/003_ocr_schema.sql) | Migración | Tablas OCR en Supabase |
| [`migrations/004_docx_schema.sql`](migrations/004_docx_schema.sql) | Migración | Bloques DOCX |
| [`plan-fase-b.md`](plan-fase-b.md) | Histórico | Pipeline B1–B7 (cerrado) |
| [`plan-pptx-extraction.md`](plan-pptx-extraction.md) | Histórico | PPTX jerárquico (cerrado) |
| [`plan-docx-extraction.md`](plan-docx-extraction.md) | Histórico | DOCX jerárquico (cerrado) |
