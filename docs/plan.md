# MMi by Monitoring — Plan de implementación

**Producto:** memoria técnica industrial (buscar y citar documentos).  
**Recorte MVP:** RAG documental sobre corpus NCC30/ODS1. **Motor MMI** (activo + síntoma + hipótesis) planificado en [`plan-mmi-motor.md`](plan-mmi-motor.md). Sin agentes autónomos ni n8n en MVP.  
**Repo:** [Monitoring-ti/MMi-Monitoring](https://github.com/Monitoring-ti/MMi-Monitoring)  
**Última actualización:** 2026-09-01 (noche) — MVP operativo · Fase C ✅ · Motor M1–M6 ✅ · rama `analisis-datos`

---

## 1. Objetivo del MVP

Permitir a un usuario técnico:

1. **Buscar** fragmentos en el corpus con citas trazables (documento, versión, página/sección).
2. **Preguntar** y obtener una respuesta estructurada (Resumen + Detalle) con referencias `[1]`, `[2]`, etc.
3. **Revisar** la calidad de extracción antes de indexar (Fase 0 / QA).
4. **Seleccionar** qué archivos del corpus entran al análisis (sí/no por documento).

Principios: trazabilidad, solo versiones vigentes en el lote inicial, no inventar normas ni revisiones.

---

## 2. Estado actual (2026-09-01)

### Hecho ✅

| Área | Entregable | Ubicación |
|------|------------|-----------|
| Corpus local | ~1735 archivos escaneables (NCC30 + ODS1 + fixtures) | `corpus_picker` |
| **Selector corpus** | Árbol + filtros (tipo, ubicación, estado) + sí/no análisis + procesados | `mmi.tools.corpus_picker` → `out/corpus-picker.html` |
| Lote 1 MVP | 9 documentos Rev vigente (sin Rev 4/5) | `src/mmi/corpus/lote1.py` |
| Fase 0 PDF/Excel | Manifest idempotente + HTML revisión | `process_manifest` → `out/lote1-extract/` |
| **Fase 0 PPTX** | Jerárquico slide→elemento; FMECA 51/51, RCM 62/62 pass | `pptx*.py`, `plan-pptx-extraction.md` |
| **Fase 0 OCR** | Azure + `plan_detect`; piloto planos INF TEC | `ocr_azure.py`, `plan_detect.py` |
| **Fase 0 DOCX (B7)** | Extractor jerárquico bloques; `--docx-only` | `docx*.py`, `plan-docx-extraction.md` |
| QA por documento | pass / review / reject / excluido + acciones No rel. / Verificar | `out/review.html` |
| **Dashboard ingesta (B6)** | Fase 0 + índice + logical_key + identidad + tokens + en vivo | `review.html` |
| **Corpus ODS1** | Manifest 1582 archivos; Fase 0 masiva | `process_manifest` → `out/ods1-extract/` |
| **Indexación ODS1** | Batch incremental idempotente | `index_corpus` → `out/index-corpus-summary.json` |
| **SQL DOCX** | Bloques, tablas, media + RLS | `docs/migrations/004_docx_schema.sql` |
| Enlace nube | SharePoint/OneDrive para revisar originales | `out/source-review.html` |
| Registro tipos | Matriz central ready/planned | `file_types.py`, `file-types-compatibility.md` |
| Indexación v2 | Pipeline + B1 identidad (R1–R4) + activación atómica | `src/mmi/index/` · `plan-document-identity.md` |
| Búsqueda híbrida | Dense OpenAI + BM25 (`msvc-runtime` Windows) | `src/mmi/search/engine.py` |
| RAG respuestas | OpenRouter (`gpt-4o-mini` por defecto) | `src/mmi/search/answer.py` |
| UI búsqueda | Ejemplos corpus + fragmentos | `out/search.html` |
| **UI Consulta RAG** | Respuesta + refs + evidencia | `out/rag.html` |
| **UI revisión unificada** | Hub Fase 0 + índice | `out/review.html` |
| Servidor local | Estáticos + API | `serve_local` puerto **8773** |
| Git | Repo remoto creado; commit inicial local | GitHub `Monitoring-ti/MMi-Monitoring` |

### Parcial / pendiente operativo ⚠️

| Ítem | Estado | Acción siguiente |
|------|--------|------------------|
| **Triaje rechazados ODS1** | ✅ 47 reject · 100 excluidos | — |
| **Fase 0 ODS1** | ✅ **1435 pass · 0 review** | — |
| **Indexación ODS1** | ✅ ~1096 activos · ~65k chunks · 0 err | Validación RAG |
| Identidad documental (B1) | ✅ pipeline + CLI + dashboard | — |
| **B2 cola etapas** | ✅ incl. `--resume-failed` (B2.7) | — |
| **B4 catálogo EAM** | ✅ **1482 tags · 100% cobertura** | `catalog_sync` · `catalog-validation.html` |
| **Validación RAG** | ✅ **10/10 casos OK** | `validate_rag` · `out/rag-validation.html` |
| **Motor MMI** | ✅ M1–M6 | piloto completo |
| `.xlsm` (~119) | No soportados | Fase C o conversión |
| Reranker C1 | ✅ léxico + tags | `search/rerank.py` |
| Conflictos C2 | ✅ `/api/ask` + `rag.html` | `search/conflicts.py` |
| Golden set C3 | ✅ 35 casos · MRR 0.95 | `eval_retrieval` |

### API local

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/search.html` | Búsqueda fragmentos |
| GET | `/rag.html` | Consulta RAG con citas |
| GET | `/motor.html` | Motor MMI — activo + síntoma |
| GET | `/review.html` | Dashboard revisión (canónico) |
| POST | `/api/search` | Fragmentos sin redactar |
| POST | `/api/ask` | Respuesta + `ask_id` |
| POST | `/api/motor/analyze` | Análisis activo + síntoma |
| POST | `/api/motor/details` | Fuentes / evidencia motor |
| GET/POST | `/api/ingestion-action` | Excluir, no relevante, re-extraer, IA |
| GET | `/api/ingestion-live` | Snapshot en vivo dashboard |
| GET/POST | `/api/remote-source` | Enlace carpeta SharePoint/OneDrive |

---

## 3. Arquitectura (MVP)

```
Corpus local (ODS1 TORR ENF DCH — 1582 indexables en manifest)
    → process-manifest.json (lote ods1-full)
    → Fase 0 masiva → out/ods1-extract/
    → index_corpus (batch idempotente)
    → review.html (dashboard Fase 0 + índice)
        → Qdrant (vectores)
        → Supabase (documents, chunks, metadatos)
    → search.html / rag.html / motor.html (consulta)
    → corpus_picker (selección sí/no por lote futuro)
    → HybridSearchEngine (dense + BM25/RRF)
    → /api/ask → OpenRouter
    → serve_local (UI + APIs)
```

**Variables de entorno** (`.env`, gitignored): `SUPABASE_*`, `QDRANT_*`, `OPENAI_API_KEY`, `OPENROUTER_*`, `AZURE_DOCUMENT_INTELLIGENCE_*`.

---

## 4. Lote 1 — documentos MVP

Definido en `src/mmi/corpus/lote1.py`:

| Documento | Tipo | Fase 0 | Index |
|-----------|------|--------|-------|
| NCC-030 REV02 | norma | ✅ pass | duplicado |
| GUIGS-00001 Rev 6 | guía | ✅ pass | duplicado |
| PROGS-0001 | sop | ✅ pass | duplicado |
| Anexo C Checklist | tabla | ✅ pass | ⚠️ error onnx |
| FRMGS-0035 FMECA | tabla | ❌ reject | — |
| FRMGS-0036 RCM | tabla | ✅ pass | duplicado |
| FMECA capacitación | presentación | ✅ pass 51/51 | ✅ indexado |
| RCM capacitación | presentación | ✅ pass 62/62 | ✅ indexado |
| IFC 078 REV15 | sop (instructivo) | ✅ pass · PDF nativo | duplicado (57 chunks) |

**Resumen Fase 0 lote 1:** 8 pass · 1 reject · 0 pendientes extractor. **Indexación lote 1:** ✅ completa.

### Corpus ODS1 (operativo — `out/analysis-status.json`)

| Métrica | Valor (2026-09-01) |
|---------|---------------------|
| Manifest | ~1.582 archivos |
| Fase 0 OK | **1435 pass** |
| Rechazados | 47 |
| Indexados | **1274** |
| Err. índice / pend. | **0 / 0** |
| Catálogo EAM | 1482 tags · 100% cobertura |

---

## 5. Fases y checklist

### Fase 0 — Extracción y QA

- [x] Inventario corpus + picker árbol con filtros
- [x] Selección sí/no por archivo + estado procesado en directorio
- [x] Extractor PDF con texto nativo
- [x] Extractor Excel (headers, sheet/row, anclas)
- [x] Extractor **PPTX** jerárquico (FMECA/RCM)
- [x] **OCR Azure** + detección planos (`plan_detect`)
- [x] Extractor **DOC/DOCX** jerárquico (B7)
- [x] Manifest + visor HTML por documento
- [x] Dashboard estado análisis + enlace nube
- [x] Dashboard ingesta Fase 0 + índice + logical_key + identidad dudosa
- [x] Triaje rechazados completo
- [x] Indexación ODS1 batch completa (1274 indexados, 0 err pendientes)
- [ ] Fase 0 pendientes extractor (~18 tipos no soportados, p. ej. `.xlsm`)
- [ ] Re-indexación limpia (solo Rev vigente en búsqueda)

### Fase 1 — Indexación

- [x] Chunking + embeddings OpenAI
- [x] Pipeline Qdrant + Supabase
- [x] CLI `index_lote1`
- [x] Detección duplicados SHA-256 (R1)
- [x] Identidad documental B1 (logical_key, content_hash, needs_review)
- [x] Indexar batch ODS1 (`index_corpus`)
- [x] Indexación masiva pass (`index_corpus` — 1274 activos)
- [x] Cola `ingestion_jobs` por etapas (B2) + `ingest_worker`
- [ ] Reintentar histórico 308 err (opcional; cola actual en 0 err)
- [ ] **Re-indexación limpia** (`reindex_clean` — excluir Rev antiguas del índice)

### Fase 2 — Búsqueda y RAG

- [x] Motor híbrido dense + BM25
- [x] Respuesta estructurada con citas (`rag.html`)
- [x] Ejemplos de consulta anclados al corpus ODS1
- [x] BM25 estable Windows (`msvc-runtime` + reindex lote 1)
- [x] Nav unificada revisión + búsqueda + RAG
- [ ] Prueba de carga periódica documentada
- [x] Golden set / evaluación recall (`eval_retrieval` · 35 casos C3)
- [x] Reranker C1 (`search/rerank.py`)
- [x] Conflictos C2 (`/api/ask` · banner `rag.html`)
- [ ] Filtros UI: tipo, dominio, criticidad
- [x] **Motor MMI** — consulta por activo + síntoma ([`plan-mmi-motor.md`](plan-mmi-motor.md))
  - [x] M1 UI `motor.html`
  - [x] M2 API `/api/motor/analyze`
  - [x] M3 Hechos verificados (dato + documento)
  - [x] M4 Hipótesis rankeadas + confianza
  - [x] M5 Verificación física + export PDF
  - [x] M6 Discrepancias + histórico EAM

### Fase C — OCR y calidad (ver `plan-fase-c.md`)

- [x] C1 Reranker · C2 Conflictos · C3 Golden set
- [x] C4 núcleo OCR (Azure, staging, validación, `plan_detect`)
- [x] C4.13 Piloto plano INF TEC indexado
- [ ] C4.14 PPTX visual → OCR región
- [ ] C5 Cola async (opcional)

### Fase D — Análisis de datos (rama `analisis-datos`)

Ver [`plan-analisis-datos.md`](plan-analisis-datos.md): cobertura corpus, calidad Fase 0, métricas golden set, inventario planos.

### Fase 3 — Producto

- [ ] Auth multi-tenant
- [ ] Despliegue cloud
- [ ] Rotación claves expuestas
- [ ] Archivar o unificar `manus308/` (referencia Manus)

---

## 6. Comandos operativos

```powershell
cd mmi-by-monitoring
.venv\Scripts\python -m pip install -e .

# Selector corpus (filtros + sí/no análisis)
.venv\Scripts\python -m mmi.tools.corpus_picker --serve          # :8770
.venv\Scripts\python -m mmi.tools.corpus_picker --write-html out\corpus-picker.html

# Fase 0 — corpus ODS1 (por defecto)
.venv\Scripts\python -m mmi.tools.process_manifest --write-only
.venv\Scripts\python -m mmi.tools.process_manifest
.venv\Scripts\python -m mmi.tools.process_manifest --limit 50   # piloto
.venv\Scripts\python -m mmi.tools.process_manifest --lote1    # solo 9 docs MVP

# Fase 0 — filtros por tipo
.venv\Scripts\python -m mmi.tools.process_manifest --pdf-only
.venv\Scripts\python -m mmi.tools.process_manifest --pptx-only
.venv\Scripts\python -m mmi.tools.process_manifest --docx-only

# Estado QA + ingesta (rápido, sin review pages)
.venv\Scripts\python -m mmi.tools.analysis_status --skip-reviews

# Indexación
.venv\Scripts\python -m mmi.tools.index_corpus --resume
.venv\Scripts\python -m mmi.tools.index_corpus --retry-errors
.venv\Scripts\python -m mmi.tools.ingest_worker --limit 5
.venv\Scripts\python -m mmi.tools.index_corpus --limit 20
.venv\Scripts\python -m mmi.tools.index_lote1
.venv\Scripts\python -m mmi.tools.reindex_clean --dry-run
.venv\Scripts\python -m mmi.tools.reindex_clean --reindex

# OCR / planos (Fase C)
.venv\Scripts\python -m mmi.tools.plan_scan --plano-only --out out\plan-scan.json
.venv\Scripts\python -m mmi.tools.ocr_worker --ifc
.venv\Scripts\python -m mmi.tools.eval_retrieval --compare-rerank

# Servidor (usar siempre para UI con APIs)
.venv\Scripts\python -m mmi.tools.serve_local --port 8773

# Reporte tipos
.venv\Scripts\python -m mmi.tools.file_types_report --corpus "ODS1 TORR ENF DCH/00 DOCUMENTOS NCC30"

# Prueba de carga (búsqueda directa → reporte HTML)
.venv\Scripts\python -m mmi.tools.load_test --requests 30 --concurrency 4
.venv\Scripts\python -m mmi.tools.load_test --requests 20 --http --extract
# Con API local (serve_local en :8773) + ask OpenRouter:
.venv\Scripts\python -m mmi.tools.load_test --requests 12 --http --ask
```

**URLs locales (serve_local :8773)**

| Página | URL |
|--------|-----|
| Búsqueda | http://127.0.0.1:8773/search.html |
| Consulta RAG | http://127.0.0.1:8773/rag.html |
| Revisión (hub) | http://127.0.0.1:8773/review.html |
| Motor MMI | http://127.0.0.1:8773/motor.html |
| Identidad dudosa | http://127.0.0.1:8773/review.html?index=needs_review |
| Legacy ingesta | http://127.0.0.1:8773/ingestion-status.html → redirect |
| Corpus (estático) | http://127.0.0.1:8773/corpus-picker.html |
| Enlace nube | http://127.0.0.1:8773/source-review.html |
| Reporte carga | http://127.0.0.1:8773/load-test-report.html |

---

## 7. Qué falta (gap actual)

Priorizado por impacto en el MVP. Lo demás es deuda opcional o Fase 3.

### 🟡 Siguiente sprint (Fase C — OCR)

| # | Ítem | Por qué | Comando / artefacto |
|---|------|---------|---------------------|
| 1 | **plan_scan** corpus completo | Inventario planos vs documentos | `plan_scan --subdir "02 INF TEC" --out out/plan-scan.json` |
| 2 | Persistencia `ocr_*` en Supabase | Trazabilidad producción | aplicar `003_ocr_schema.sql` + `ocr_store` PG |
| 3 | **C4.14** — PPTX visual → OCR región | Diapos con gráficos sin texto | `pptx_visual.py` |
| 4 | Escala OCR a más planos INF TEC | Tras piloto `4600027995-06950-201ME-00001` | `ocr_index_pilot` / batch worker |

### 🟡 Calidad búsqueda / gobernanza

| # | Ítem | Estado |
|---|------|--------|
| 5 | Filtros UI búsqueda (tipo, dominio, criticidad) | pendiente |
| 6 | `validation_status=pass` por defecto en producción | pendiente |
| 7 | C3.3 CI golden set en PR | pendiente |
| 8 | Re-indexación limpia Rev vigente (`reindex_clean`) | pendiente |
| 9 | Prueba de carga periódica documentada | pendiente |

### 🟢 Deuda baja / opcional

| # | Ítem |
|---|------|
| 10 | Soporte `.xlsm` (~119 archivos) o conversión |
| 11 | FMECA lote1 reject (1 Excel) — revisar manual |
| 12 | C5 cola async (Redis) si volumen crece |
| 13 | Rotación claves expuestas en chat |

### ⏳ Fase 3 — Producto

Auth multi-tenant · despliegue cloud · archivar `manus308/`.

---

## 8. Prioridades (referencia rápida)

### Cerrado ✅

| Área | Métrica |
|------|---------|
| Fase 0 ODS1 | 1435 pass |
| Índice | 1274 docs · 0 err pendientes |
| RAG validación | 10/10 casos |
| Golden set C3 | 35/35 recall@5 · MRR ~0.95 |
| Motor MMI | M1–M6 |
| C1–C2 | Reranker + conflictos en RAG |

### En curso 🔄

| Bloque | Pendiente clave |
|--------|-----------------|
| C4 OCR | Indexar planos INF TEC tras `plan_detect` |
| C4 | PPTX visual · tablas `ocr_*` en PG |

---

## 9. Decisiones cerradas

| Tema | Decisión |
|------|----------|
| Identidad documental | Tres capas: `file_hash` (archivo) · `logical_key`/`document_key` (doc) · versión (`documents` + label). Ver `plan-document-identity.md` |
| Vector DB | Qdrant Cloud |
| Metadatos | Supabase (Postgres REST) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Generación MVP | OpenRouter (`openai/gpt-4o-mini`) |
| OCR piloto | Azure Document Intelligence |
| Integración | APIs Python directas, sin n8n |
| Lote inicial | Solo revisiones vigentes Rev 6 / REV02 |
| Selección corpus | Checkbox = sí al análisis; manifest guarda incluidos y excluidos |

---

## 10. Riesgos conocidos

- **Servidor incorrecto en 8773** → 404 en `/api/ask`; usar `serve_local`.
- **HTML vía `file://`** → APIs no disponibles.
- **Corpus mixto en índice** → hits Rev antigua hasta `reindex_clean`.
- **BM25 Windows** → `msvc-runtime` en venv; reindexar tras activar sparse.
- **Claves expuestas en chat** → rotar OpenAI, Supabase, Qdrant, OpenRouter, Azure.
- **Git SSH** → push pendiente configuración clave.

---

## 11. Referencias

| Doc | Contenido |
|-----|-----------|
| `docs/plan-fase-b.md` | Pipeline ordenado B1–B7 |
| `docs/plan-document-identity.md` | Identidad: file_hash · logical_key · versión |
| `docs/plan-fase-c.md` | Reranker, golden set, conflictos |
| **`docs/plan-mmi-motor.md`** | **Motor MMI: activo + síntoma + hipótesis + verificación** |
| `docs/plan-fase-c-ocr.md` | OCR con incertidumbre |
| `docs/plan-pptx-extraction.md` | PPTX jerárquico ✅ |
| `docs/plan-docx-extraction.md` | DOCX jerárquico ✅ |
| `docs/migrations/004_docx_schema.sql` | SQL bloques DOCX |
| `docs/file-types-compatibility.md` | Matriz tipos |
| `docs/plan-ingesta.md` | Fase A diagnóstico |
| `manus308/` | Referencia plan Manus v3 |
