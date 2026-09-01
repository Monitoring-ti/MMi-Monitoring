# Fase B — Plan operativo de ingesta MMI

**Fecha:** 2026-08-31  
**Precondición:** migración `002_ingestion_v2.sql` aplicada en Supabase ✅  
**Objetivo:** dejar el pipeline **ordenado, reanudable y observable** — sin reprocesar, con cola de trabajos, metadatos validados y corpus ODS1 completo.

**Sprint activo:** Motor MMI piloto M1–M6 cerrado ✅

---

## 0. Estado al 2026-09-01

| Bloque | Estado | Notas |
|--------|--------|-------|
| **B0–B7 + ODS1** | ✅ cerrado | Ver tabla histórica abajo |
| **Validación RAG** | ✅ 10/10 | `validate_rag` |
| **B4 catálogo EAM** | ✅ 1482 tags · 100% | `catalog_sync` |
| **Motor MMI** | ✅ M1–M6 | discrepancias · EAM · export PDF |

### Acción inmediata — Motor MMI

```powershell
.venv\Scripts\python -m mmi.tools.serve_local --port 8773
# → http://127.0.0.1:8773/motor.html?asset=CTS-DCH-ENF&q=alta+temperatura+caudal
```

**Criterio M6:** PT-882 calibración vencida, WO-88912 en histórico EAM, banner discrepancias.

---

## 1. Punto de partida (referencia)

| Capa | Estado |
|------|--------|
| SQL v2 | `document_catalog`, `ingestion_jobs`, `chunk_metadata`, `catalog_assets` |
| Fase 0 | Idempotente por `file_hash`; PDF/Excel/PPTX/OCR/DOCX |
| Identidad B1 | `file_hash` dup · `logical_key` · `content_hash` · R1–R4 en pipeline |
| Selector | `include_in_analysis` + estado procesado por directorio |
| Indexación v2 | Estados + activación atómica + skip `mismo_contenido` |
| Búsqueda | Filtro `is_current` + `version_status=active` |
| Pendiente operativo | Cola B2, catálogo EAM B4, re-index limpio |

---

## 2. Arquitectura objetivo (todo ordenado)

Ver diagrama en § B2. Hoy el flujo monolítico (`ingest_file`) ya aplica B1; falta partir en etapas reanudables.

---

## 3. Fase B — entregables (6 bloques)

### B1 — Detección de versiones ✅

**Especificación:** [`docs/plan-document-identity.md`](plan-document-identity.md)

| Tarea | Estado |
|-------|--------|
| B1.2 `version_detect.py` + CLI dry-run | ✅ |
| B1.3 Skip embed si `content_hash` igual | ✅ pipeline |
| B1.4 Nueva versión + supersede | ✅ pipeline |
| B1.5 `needs_review` | ✅ jobs + dashboard |
| B1.6 Métricas en `ingestion_jobs` | ✅ |

**Comandos:**

```powershell
.venv\Scripts\python -m mmi.tools.version_detect --manifest out/process-manifest.json --limit 100
.venv\Scripts\python -m mmi.tools.index_corpus
```

---

### B2 — Cola de trabajos ⚠️ **sprint activo**

| Tarea | Estado |
|-------|--------|
| B2.1 `stages.py` validate/extract/chunk | ✅ |
| B2.2 `ingest_worker.py` preview CLI | ✅ |
| B2.3 `stage_embed` + vectores dense/sparse | ✅ |
| B2.4 `stage_index` Qdrant + chunks PG | ✅ |
| B2.5 `stage_activate` + `run_full_ingest` | ✅ |
| B2.6 Worker `--execute` | ✅ |
| B2.7 Reanudar job fallido desde etapa | ✅ |

**Archivos:** `src/mmi/index/stages.py` · `src/mmi/tools/ingest_worker.py`

**DoD B2:** un archivo indexable corre validate→activate vía `ingest_worker --execute`. Reanudar job fallido con `ingest_worker --resume-failed --execute`.

**B2.7:** hidrata `document_id`/chunks desde PG · detecta etapa (`extract`/`embed`/`validate_index`) · `--document-id` opcional.

---

### B3 — Extractor PPTX ✅

Ver [`docs/plan-pptx-extraction.md`](plan-pptx-extraction.md).

---

### B4 — Metadatos + catálogo EAM ✅

| Tarea | Estado |
|-------|--------|
| B4.1 Enriquecer manifest (`asset_tag`, `modulo`, `codigo_documento`, `numero_guia`) | ✅ `enrich_manifest_asset_tags` |
| B4.2 `derive_logical_key()` en manifest | ✅ `manifest_index.py` |
| B4.3 Validación manifest ↔ `catalog_assets` | ✅ `validate_manifest_catalog` |
| B4.4 CLI sync enrich + seed + reporte | ✅ `catalog_sync.py` |
| B4.5 `asset_tag`/`modulo` en payload Qdrant + ingest | ✅ `stages.py` · `manifest_index` |

**Comando:**

```powershell
.venv\Scripts\python -m mmi.tools.catalog_sync
# → http://127.0.0.1:8773/catalog-validation.html
```

**DoD B4 (2026-09-01):** 1482 docs en análisis · 100% tags válidos en PG · reporte HTML/JSON.

---

### B6 — Dashboard unificado ✅

| Vista | Contenido |
|-------|-----------|
| `review.html` | Fase 0 + índice + logical_key + identidad + tokens + acciones |
| Filtros índice | active, duplicado, mismo_contenido, needs_review, error |
| En vivo | `/api/ingestion-live` |

| Tarea | Estado |
|-------|--------|
| B6.1–B6.4 Dashboard Fase 0 + índice | ✅ |
| B6.5 Columna logical_key + filtro identidad dudosa | ✅ |

**URLs:**

- General: `http://127.0.0.1:8773/review.html?status=all`
- Identidad dudosa: `?index=needs_review`

---

### B7 — Extractor DOC/DOCX ✅

Ver [`docs/plan-docx-extraction.md`](plan-docx-extraction.md).

---

## 4. Orden de implementación (sprints)

### Sprint ODS1 — cerrado ✅

- Fase 0: 1513 pass · index 365 activos · búsqueda piloto OK

### Sprint actual — Fase B 🔄

| # | Entregable | Comando / artefacto |
|---|------------|---------------------|
| 1 | **B2.3–B2.6** embed/index/activate en worker | `stages.py` + `ingest_worker --execute` |
| 2 | **Backlog índice** 308 err | `index_corpus --retry-errors` |
| 3 | **Fase 0** 18 pend. extractor | `process_manifest` |
| 4 | **B4** catálogo EAM mínimo | `catalog/assets.py` + validación manifest |
| 5 | Re-index limpio Rev vigente | `reindex_clean` (opcional) |

### Sprint siguiente — Fase 2 / Motor (no bloqueante)

- Validar `search.html` / `rag.html` sobre corpus indexado
- Motor MMI M1 UI — ver [`plan-mmi-motor.md`](plan-mmi-motor.md)

---

## 5. Referencias

- Identidad documental: `docs/plan-document-identity.md`
- Plan general: `docs/plan.md`
- SQL v2: `docs/migrations/002_ingestion_v2.sql`
