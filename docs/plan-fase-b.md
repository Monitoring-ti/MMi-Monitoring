# Fase B — Plan operativo de ingesta MMI

**Fecha:** 2026-08-31  
**Precondición:** migración `002_ingestion_v2.sql` aplicada en Supabase ✅  
**Objetivo:** dejar el pipeline **ordenado, reanudable y observable** — sin reprocesar, con cola de trabajos, metadatos validados y corpus lote 1 completo.

---

## 1. Punto de partida (hoy)

| Capa | Estado |
|------|--------|
| SQL v2 | `document_catalog`, `ingestion_jobs`, `chunk_metadata`, `catalog_assets` |
| Fase 0 | Idempotente por `file_hash` en `extracted.json` |
| Indexación v2 | Estados + activación atómica + `content_hash` |
| Búsqueda | Filtro `is_current` + `version_status=active` |
| Pendiente operativo | Re-index limpio lote 1, PPTX, cola por etapas, dashboards unificados |

### Acción inmediata (antes de B1)

```powershell
# 1. Ver qué se eliminaría del índice viejo
.venv\Scripts\python -m mmi.tools.reindex_clean --dry-run

# 2. Limpiar + re-indexar solo lote 1 Rev vigente
.venv\Scripts\python -m mmi.tools.reindex_clean --reindex

# 3. Verificar Fase 0 (solo cambios)
.venv\Scripts\python -m mmi.tools.process_manifest

# 4. Confirmar jobs en Supabase
#    SELECT status, count(*) FROM documents GROUP BY status;
#    SELECT * FROM ingestion_jobs ORDER BY started_at DESC LIMIT 20;
```

**Criterio de salida:** todos los documentos activos del tenant `monitoring` tienen `document_key` del lote 1, `status=active`, `is_current=true`, sin restos Rev 4/5 en Qdrant.

---

## 2. Arquitectura objetivo (todo ordenado)

```
┌─────────────────────────────────────────────────────────────────┐
│  RECEPCIÓN                                                        │
│  manifest / upload → validación → SHA-256 → content_hash         │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  REGISTRO (Supabase)                                              │
│  document_catalog ←→ documents (versión) ← ingestion_jobs        │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  PIPELINE POR ETAPAS (reanudable)                                 │
│  extract → validate_meta → chunk → embed → index → validate →   │
│  activate                                                         │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  ALMACENAMIENTO                                                   │
│  chunks + chunk_metadata │ Qdrant (dense + sparse)                │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  OBSERVABILIDAD                                                   │
│  analysis-status.html │ ingestion-status.html │ registry JSON    │
└─────────────────────────────────────────────────────────────────┘
```

### Módulos Python (estructura final)

```
src/mmi/
  ingest/
    pdf.py, excel.py, pptx.py      # extractores Fase 0
    pptx_models.py, pptx_normalize.py, pptx_visual.py  # PPTX jerárquico [B3]
    ports.py, ocr.py
    validate.py                    # extensión, tamaño, permisos  [B2]
  index/
    pipeline.py                    # orquestador delgado
    stages.py                      # una función por etapa         [B2]
    worker.py                      # cola ingestion_jobs           [B2]
    content_hash.py                # + slide_content_hash          [B3]
    chunking.py, pptx_chunking.py  # chunking + contexto slide     [B3/B5]
    store.py
  catalog/
    assets.py                      # catalog_assets CRUD           [B4]
    metadata.py                    # obligatorio vs extraído         [B4]
  analysis/
    status.py                      # QA Fase 0
    ingestion_status.py            # dashboard jobs/versiones        [B6]
  tools/
    process_manifest.py
    index_lote1.py
    reindex_clean.py
    ingest_worker.py               # CLI worker cola               [B2]
```

---

## 3. Fase B — entregables (6 bloques)

### B1 — Detección de versiones (`content_hash`)

**Problema:** SHA-256 igual evita duplicado físico, pero no detecta “misma guía, revisión distinta con texto casi igual”.

| Tarea | Detalle |
|-------|---------|
| B1.1 | Tras extracción, calcular `content_hash` (ya en pipeline) y persistir en `documents` |
| B1.2 | Consulta: mismo `catalog_id` + `content_hash` distinto → flag `posible_revision_menor` |
| B1.3 | Si `file_hash` nuevo pero `content_hash` igual → skip embed, solo actualizar `version_label` |
| B1.4 | Registrar decisión en `ingestion_jobs.metrics` |

**Archivos:** `src/mmi/index/content_hash.py`, `src/mmi/catalog/version_detect.py` (nuevo)  
**DoD:** CLI reporta duplicados físicos vs contenido igual vs revisión real.

---

### B2 — Cola de trabajos y reanudación por etapa

**Problema:** hoy `ingest_file` es monolítico; si falla en embed, se reprocesa todo.

| Etapa | `ingestion_jobs.stage` | Persistencia intermedia |
|-------|------------------------|------------------------|
| Recibido | `received` | job + document `received` |
| Validación | `validate` | log errores metadatos |
| Extracción | `extract` | `out/lote1-extract/` o blob |
| Chunking | `chunk` | JSON `out/staging/{doc_id}/chunks.json` |
| Embeddings | `embed` | `out/staging/{doc_id}/vectors.json` (opcional) |
| Indexación | `index` | chunks PG + Qdrant |
| Validación final | `validate_index` | conteos |
| Activación | `activate` | `status=active` atómico |

| Tarea | Detalle |
|-------|---------|
| B2.1 | Refactor `pipeline.py` → `stages.py` (funciones puras por etapa) |
| B2.2 | `worker.py`: lee jobs `status=running|failed`, reanuda desde última etapa OK |
| B2.3 | Reintentos con backoff (OpenAI, Qdrant): max 3, exponencial |
| B2.4 | CLI: `python -m mmi.tools.ingest_worker --once` y `--watch` |
| B2.5 | Deprecar `ingestion-registry.json` local (solo backup) |

**DoD:** cortar pipeline en `embed`, relanzar worker, termina sin re-extraer.

---

### B3 — Extractor PPTX (desbloquear lote 1)

**Especificación completa:** [`docs/plan-pptx-extraction.md`](plan-pptx-extraction.md)

Principio: jerarquía **presentación → sección → diapositiva → elemento → fragmento**. No tratar PPTX como texto continuo.

```
PPTX → file_hash → extracción/slide → slides.json → validación
     → texto contextualizado → chunking → embed → index → activate
```

| Tarea | Detalle |
|-------|---------|
| B3.1 | `pptx_models.py` — `SlideRecord`, `SlideElement`, `PresentationExtract` |
| B3.2 | `pptx.py` — extracción orden visual: texto, notas, tablas, charts, refs imagen |
| B3.3 | `pptx_normalize.py` — bloques contextualizados (presentación, sección, slide, metadatos) |
| B3.4 | `process_manifest` — `phase0=pptx` → `slides.json` + `extracted.json` |
| B3.5 | `pptx_chunking.py` — 1 slide simple; densas por elemento; tablas intactas; chunks por sección |
| B3.6 | `slide_content_hash` — reprocesar solo slides modificadas |
| B3.7 | `blocks.py` + `index_lote1` — rama `.pptx`; activación solo si todas las slides válidas indexadas |
| B3.8 | Análisis visual **selectivo** (stub; OCR completo en Fase C) |
| B3.9 | Citas: presentación + versión + diapositiva + elemento en payload y respuesta |

**Archivos lote 1:** `fmeca-capacitacion`, `rcm-capacitacion`  
**DoD:** ver checklist en `plan-pptx-extraction.md` §8.

---

### B4 — Metadatos obligatorios vs extraídos + catálogo EAM

**Separación (propuesta original):**

| Tipo | Campos | Validación |
|------|--------|------------|
| Obligatorios | `tenant_id`, `document_key`, `tipo`, `version_label` | Falla etapa `validate` si faltan |
| Extraídos | `asset_codes`, `section_path`, fechas, entidades | Pueden quedar `pending_review` en `chunk_metadata` |
| Catálogo | `catalog_assets.asset_tag` | Si chunk cita tag no vigente → warning, no indexar tag |

| Tarea | Detalle |
|-------|---------|
| B4.1 | `catalog/assets.py` — CRUD + import CSV stub IFC/equipos |
| B4.2 | `catalog/metadata.py` — `validate_required()`, `validate_assets()` |
| B4.3 | Poblar `chunk_metadata` al insertar chunks |
| B4.4 | Manifest enriquecido: `asset_id`, `modulo`, `origen` por archivo |

**DoD:** ingesta sin `document_key` falla antes de embed; tags desconocidos quedan en log.

---

### B5 — Chunking con contexto + eficiencia

| Tarea | Detalle |
|-------|---------|
| B5.1 | Prefijo en cada chunk: `{document_key} \| {version} \| {section} \| {pág}` |
| B5.2 | SOP: no cortar bloques advertencia/pasos (regex + merge) |
| B5.3 | Excel: header de hoja en cada fragmento (ya parcial) |
| B5.4 | Embeddings solo chunks nuevos (`chunk_content_hash`) |
| B5.5 | Variables `.env`: `MMI_EMBED_BATCH`, `MMI_QDRANT_BATCH`, `MMI_RETRY_MAX` |

**DoD:** fragmentos citables muestran documento sin abrir metadata; re-index incremental no re-embed chunks iguales.

---

### B6 — Dashboard unificado de ingesta

| Vista | Contenido |
|-------|-----------|
| `analysis-status.html` | QA Fase 0 (ya existe) |
| `ingestion-status.html` | jobs, estados versión, errores, métricas |
| `source-review.html` | Enlace SharePoint/OneDrive para revisar originales |
| Enlaces cruzados | document_key → extract review → chunks count |

### B7 — Extractor DOC/DOCX jerárquico

**Especificación:** [`docs/plan-docx-extraction.md`](plan-docx-extraction.md)  
**Matriz tipos:** [`docs/file-types-compatibility.md`](file-types-compatibility.md)

Principio: documento → sección → bloque → tabla/elemento → fragmento.

| Tarea | Detalle |
|-------|---------|
| B7.1–B7.5 | Modelos, `docx.py`, DOC→DOCX, normalización, Azure layout fallback |
| B7.6–B7.8 | Fase 0, chunking SOP/manual, fix `chunking.py` |
| B7.9–B7.10 | Review HTML + piloto Anexos GUIGS rev 4 |

**DoD:** ver checklist en `plan-docx-extraction.md` §10.

---

### B6 (continuación) — tareas dashboard

| Tarea | Detalle |
|-------|---------|
| B6.1 | `analysis/ingestion_status.py` — agrega jobs + documents por catalog |
| B6.2 | HTML tabla: archivo, key, status, chunks, tokens, coste est., acciones |
| B6.3 | Servir en `serve_local` junto a búsqueda |
| B6.4 | Filtros: failed, superseded, pending |

**DoD:** una sola URL muestra pipeline completo de un documento.

---

## 4. Orden de implementación (sprints)

### Sprint 1 — Ordenar datos existentes (1–2 días)

1. `reindex_clean --reindex`
2. Verificar estados en Supabase
3. B6 mínimo: `ingestion-status.json` desde CLI (sin HTML aún)

### Sprint 2 — Cola y etapas (3–5 días)

1. B2.1–B2.4 (`stages.py` + `ingest_worker`)
2. Métricas en `ingestion_jobs.metrics`
3. B1.2 alertas `content_hash` duplicado

### Sprint 3 — PPTX + catálogo (4–5 días)

1. B3.1–B3.5 extracción + `slides.json` + normalización contextual
2. B3.6–B3.7 chunking jerárquico + integración `blocks` / `index_lote1`
3. B3.8 hash por slide + activación atómica
4. B4.1–B4.3 validación metadatos
5. Re-run manifest + index lote 1 (FMECA + RCM)

### Sprint 4 — Calidad chunk + UI (2–3 días)

1. B5 headers contexto + reglas SOP
2. B6 HTML dashboard
3. Prueba end-to-end 9 docs lote 1

---

## 5. Tabla de estados (referencia única)

### Documento (`documents.status`)

| Estado | Visible en búsqueda | Siguiente acción |
|--------|---------------------|------------------|
| `received` | No | Iniciar worker |
| `processing` | No | Esperar etapa |
| `indexed` | No | Validar + activar |
| `active` | Sí (`is_current=true`) | — |
| `failed` | No | Revisar error, reintentar |
| `superseded` | No | Solo auditoría |

### Job (`ingestion_jobs.status`)

| Estado | Significado |
|--------|-------------|
| `running` | Etapa en curso |
| `completed` | Etapa OK |
| `failed` | Reintentar o intervención |
| `skipped` | Duplicado / sin cambios |

---

## 6. Recuperación / búsqueda (preparación Fase C)

Durante Fase B, dejar hooks listos:

- Filtro `tenant_id` + `document_key` + `catalog_assets` (B4)
- Boost exacto `asset_codes` (ya parcial en engine)
- Campo `version_status` siempre en payload Qdrant
- PPTX: payload con `slide_number`, `slide_title`, `section_title` (B3)
- Recuperación slide → contexto de sección vía chunks agrupados (B3)
- **No** implementar reranker ni detección conflictos entre versiones hasta Fase C

---

## 7. Checklist “todo ordenado”

### Datos
- [ ] Un `document_catalog` row por `document_key` lote 1
- [ ] Una versión `active` por key (resto `superseded`)
- [ ] Cero chunks huérfanos (PG count = Qdrant count por `document_id`)
- [ ] `chunk_metadata` poblado para tablas Excel

### Proceso
- [ ] Fase 0 skip si hash igual
- [ ] Index skip si SHA-256 igual
- [ ] Worker reanuda por etapa
- [ ] PPTX indexados

### Observabilidad
- [ ] `ingestion-status.html` operativo
- [ ] Métricas tokens/tiempo/coste por job
- [ ] Registry local solo backup

### Corpus
- [ ] 9/9 archivos lote 1 `active` (incl. 2 PPTX)
- [ ] FRMGS-0035 sigue `reject` (plantilla vacía)
- [ ] Búsqueda sin hits Rev 4/5

---

## 8. Comandos objetivo (post Fase B)

```powershell
# Pipeline completo ordenado
.venv\Scripts\python -m mmi.tools.process_manifest
.venv\Scripts\python -m mmi.tools.ingest_worker --once

# Estado
.venv\Scripts\python -m mmi.tools.ingestion_status --serve
.venv\Scripts\python -m mmi.tools.analysis_status --serve

# Búsqueda
.venv\Scripts\python -m mmi.tools.serve_local --port 8773
```

---

## 9. Fase C (después de B — no mezclar)

Ver **[docs/plan-fase-c.md](plan-fase-c.md)** — plan operativo completo.

| Ítem | Descripción | Spec |
|------|-------------|------|
| C1 | Reranker post-filtro | `plan-fase-c.md` §3 |
| C2 | Detección contradicciones multi-versión | `plan-fase-c.md` §4 |
| C3 | Golden set ingestión + eval recall | `plan-fase-c.md` §5 |
| C4 | OCR con incertidumbre (capas crudo/normalizado) | **[plan-fase-c-ocr.md](plan-fase-c-ocr.md)** |
| C5 | Cola async (Redis / Supabase Realtime) si volumen crece | `plan-fase-c.md` §6 |

---

## 10. Referencias

- Fase A + diagnóstico: `docs/plan-ingesta.md`
- SQL v2: `docs/migrations/002_ingestion_v2.sql`
- Plan MVP: `docs/plan.md`
- PPTX jerárquico: `docs/plan-pptx-extraction.md`
- Fase C: `docs/plan-fase-c.md` · OCR: `docs/plan-fase-c-ocr.md`
- Propuesta ampliada: conversación 2026-08-31 (documento/versión/fragmento/estado)
