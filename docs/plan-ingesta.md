# Plan de mejora — Ingesta MMI

**Fecha:** 2026-08-31  
**Base:** propuesta ampliada (documento / versión / fragmento / estado) + código actual en `src/mmi/`  
**Objetivo:** precisión, no duplicar trabajo, activación atómica de versiones, trazabilidad EAM/CMMS.

---

## 1. Diagnóstico — qué hay hoy

### Flujo actual (simplificado)

```
manifest lote1 → Fase 0 (PDF/Excel) → QA (analysis-status)
    → ingest_file() → chunks + embeddings + Qdrant + Supabase documents/chunks
```

### Archivos clave

| Componente | Ruta | Rol |
|------------|------|-----|
| Manifest | `mmi.tools.process_manifest` | Lista lote 1, extrae a `out/lote1-extract/` |
| QA | `mmi.analysis.status` | pass / reject / pendiente |
| Indexación | `mmi.index.pipeline.ingest_file` | SHA-256 → skip duplicado en Supabase |
| Store | `mmi.index.store` | `documents` + `chunks` (plano) |
| Chunking | `mmi.index.chunking` | Por tipo (SOP ~550, tabla ~350, guía ~900 tokens) |

### Qué ya funciona

- **SHA-256 en indexación:** `pg_find_document(tenant, file_hash)` → estado `duplicado` sin re-embed.
- **QA Fase 0:** no indexa si `quality != pass` en `extracted.json`.
- **Embeddings en lotes** de 64 (`pipeline.py`).
- **Chunks masivos** a Postgres en lotes de 500.
- **Herencia parcial de contexto** en chunk: `section_path`, página, `asset_codes`, `criticality_level`.

### Brechas respecto a la propuesta

| Tema | Hoy | Riesgo |
|------|-----|--------|
| Modelo datos | `documents` plano con `file_hash`, `is_current` en documento | Varias revisiones del mismo doc lógico no modeladas; `is_current` en chunk y documento mezclados |
| Fase 0 | **Re-extrae siempre** aunque el archivo no cambió | Tiempo y sobrescritura innecesaria |
| Estados | `duplicado` / `indexado` / `error` (CLI) | Sin `received` → `processing` → `indexed` → `active` → `failed` / `superseded` |
| Activación | `is_current=True` al insertar documento | Nueva versión puede quedar activa antes de validar todos los chunks |
| Huella contenido | Solo SHA-256 binario | No detecta revisiones menores con mismo layout |
| Metadatos | `tipo`, `dominio`, `version_label` opcional | Sin validación EAM/CMMS ni `catalog_assets` |
| Cola | Proceso síncrono en CLI | Sin `ingestion_jobs`, reintentos ni reanudación por etapa |
| PPTX | Pendiente extractor | 2 archivos lote 1 bloqueados — ver [plan-pptx-extraction.md](plan-pptx-extraction.md) |
| Búsqueda | Filtro `is_current` en payload Qdrant | Versiones antiguas pueden seguir en índice si se indexó Rev 4/5 |

**Riesgo principal (coincide con la propuesta):** se indexa después de extraer, pero **antes** de validar identidad lógica del documento, versión canónica y metadatos obligatorios contra catálogo.

---

## 2. Modelo objetivo (separación lógica)

### Entidades

```
documents          → identidad lógica (document_key, tipo, activo, origen)
document_versions  → binario, SHA-256, content_hash, rev, fechas, estado, is_current
chunks             → texto, posición, tokens, version_id (no document_id directo para vigencia)
chunk_metadata     → tenant, asset_tag, módulo, tipo documental, vigencia, entidades NER
ingestion_jobs     → etapa, reintentos, métricas, error, duración
catalog_assets     → tags EAM/CMMS autorizados (validación obligatoria)
```

### Reglas de vigencia

- `is_current` vive en **`document_versions`**, no en cada chunk.
- Los chunks **heredan** vigencia vía `version_id` → join a versión activa.
- Búsqueda operativa: filtro por defecto `version.is_current = true` y `version.status = 'active'`.
- Versiones `superseded` se conservan para auditoría; excluidas del retrieval por defecto.

### Estados de versión

| Estado | Significado |
|--------|-------------|
| `received` | Archivo registrado, sin extraer |
| `processing` | Extracción / chunking / embeddings en curso |
| `indexed` | Fragmentos y vectores persistidos; pendiente validación |
| `active` | Validación OK; única versión `is_current` para ese `document_id` |
| `failed` | Error en cualquier etapa; no visible en búsqueda |
| `superseded` | Reemplazada por otra versión `active` |

### Activación atómica

Transacción lógica al pasar a `active`:

1. Validar conteo chunks Postgres = puntos Qdrant para `version_id`.
2. Validar metadatos obligatorios (tenant, tipo, document_key, vigencia).
3. Marcar versiones anteriores del mismo `document_id` como `superseded`, `is_current=false`.
4. Marcar nueva versión `active`, `is_current=true`.
5. Actualizar payload Qdrant (`is_current` / `version_status`) en batch.

Si falla cualquier paso → permanece en `indexed` o `failed`; **nunca** `active` parcial.

---

## 3. Flujo de carga objetivo

```
1. Recepción      → ingestion_job + document_version(received)
2. Validación     → extensión, tamaño, permisos, tenant
3. Huella binaria → SHA-256 → duplicado exacto → skip o vincular
4. Detección      → content_hash normalizado → posible nueva revisión
5. Registro       → documents (si nuevo) + version(processing)
6. Extracción     → PDF / Excel / PPT → contenido normalizado (reusar Fase 0 si hash igual)
7. Metadatos      → obligatorios vs extraídos (validar catálogo EAM)
8. Segmentación   → chunking por tipo (reglas §4)
9. Embeddings     → lotes configurables; solo contenido nuevo
10. Indexación    → bulk insert chunks + Qdrant upsert
11. Validación    → conteos, metadatos, QA humano si review
12. Activación    → active atómico (§ activación)
```

---

## 4. Chunking (ajuste sobre lo actual)

| Tipo | Tokens objetivo | Regla |
|------|-----------------|-------|
| SOP / procedimiento | 500–800 | No separar precondiciones, pasos, advertencias, criterios de aceptación |
| Excel / tabla | 300–400 | Encabezado en cada fragmento; ancla `sheet`, fila, rango |
| Guía / norma / manual | 800–900 | Por capítulo / sección (`section_path`); sin cortes arbitrarios |
| Presentación | 400–500 | Por diapositiva o bloque temático |
| Reporte fallas (futuro) | variable | Equipo + fecha + síntoma + causa + acción + resultado |

**Contexto mínimo en cada chunk (header prefijo):**

`{document_key} | {version_label} | {section_path} | pág./hoja | {asset_tags}`

---

## 5. Eficiencia y no duplicar trabajo

### Corto plazo (sin migración de schema)

| Mejora | Acción |
|--------|--------|
| Skip Fase 0 | Si `extracted.json` existe y `file_hash` coincide → `skipped` |
| Skip indexación | Ya existe vía SHA-256 en Supabase |
| Registry local | `out/ingestion-registry.json` con hash, etapa, timestamps (puente hasta `ingestion_jobs`) |
| Reprocesar solo cambios | Comparar hash; si cambió → nueva carpeta extract + nueva versión |

### Medio plazo

- Cola `ingestion_jobs` (Supabase o Redis local).
- Etapas persistidas: `extract_done`, `chunk_done`, `embed_done`, `index_done`.
- Reanudar desde última etapa OK.
- Paralelo por archivo; orden estricto dentro de una versión.
- Métricas: tiempo, tokens, chunks, coste estimado por documento.

### Largo plazo

- `content_hash` (texto normalizado: lowercase, espacios, sin headers de página).
- Similitud fuzzy para detectar revisiones menores.
- Embeddings incrementales (diff de chunks por hash de contenido).

---

## 6. Recuperación (alineado a ingesta)

1. Filtros obligatorios: `tenant_id`, activo, módulo, `version.status=active`.
2. Híbrido dense + BM25 (ya en `engine.py`).
3. Boost tags / códigos exactos (parcialmente con `asset_codes`).
4. Reranker **después** del filtro (prioridad posterior).
5. Conflicto entre versiones activas o fuentes misma prioridad → respuesta explícita + escalado humano (CoVe).

---

## 7. Plan de implementación por fases

### Fase A — Alta prioridad ✅ implementado + SQL 002 aplicado en Supabase

Ejecutar `reindex_clean --reindex` para alinear índice con lote 1 vigente.

### Fase B — Plan operativo detallado

Ver **[docs/plan-fase-b.md](plan-fase-b.md)** — 6 bloques (content_hash, cola por etapas, PPTX, catálogo EAM, chunking+eficiencia, dashboard), 4 sprints, checklist final.

| # | Bloque | Entregable |
|---|--------|------------|
| B1 | `content_hash` + detección revisiones | `version_detect.py` |
| B2 | Cola `ingestion_jobs` por etapa | `stages.py`, `ingest_worker` |
| B3 | Extractor PPTX jerárquico | [plan-pptx-extraction.md](plan-pptx-extraction.md) — 2 capacitaciones indexadas |
| B4 | `catalog_assets` + metadatos obligatorios | `chunk_metadata` |
| B5 | Chunk con contexto + embed incremental | headers + `.env` batch |
| B6 | Dashboard ingesta | `ingestion-status.html` |

### Fase C — Posterior

Ver **[docs/plan-fase-c.md](plan-fase-c.md)** y OCR detallado **[docs/plan-fase-c-ocr.md](plan-fase-c-ocr.md)**.

| # | Bloque | Entregable |
|---|--------|------------|
| C1 | Reranker post-filtro | Mejor orden tras híbrido |
| C2 | Contradicciones multi-versión | Alertas en `/api/ask` |
| C3 | Golden set + eval | `eval_retrieval.py` |
| C4 | OCR con incertidumbre | Azure DI + capas crudo/normalizado · SQL `003_ocr_schema` |
| C5 | Cola async | Redis / Realtime (opcional) |

Piloto OCR: `IFC-078` (lote 1). Migración: `docs/migrations/003_ocr_schema.sql`.

---

## 8. Esquema SQL propuesto (borrador)

```sql
-- documents: identidad lógica
create table documents (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id),
  document_key text not null,          -- ej. SGP-07MYC-GUIGS-00001
  titulo text not null,
  tipo text not null,
  dominio text,
  asset_id uuid references catalog_assets(id),
  origen text,
  created_at timestamptz default now(),
  unique (tenant_id, document_key)
);

-- document_versions: cada archivo subido
create table document_versions (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id),
  version_label text,
  file_hash text not null,             -- SHA-256 binario
  content_hash text,                   -- huella texto normalizado
  source_path text,
  extraction_method text,
  status text not null default 'received'
    check (status in ('received','processing','indexed','active','failed','superseded')),
  is_current boolean not null default false,
  error_message text,
  received_at timestamptz default now(),
  activated_at timestamptz,
  unique (tenant_id, file_hash)        -- vía join o columna tenant_id
);

-- chunks: referencia version_id (migrar desde document_id)
alter table chunks add column version_id uuid references document_versions(id);

-- ingestion_jobs
create table ingestion_jobs (
  id uuid primary key default gen_random_uuid(),
  version_id uuid references document_versions(id),
  stage text not null,
  status text not null,
  attempt int default 0,
  metrics jsonb,
  error text,
  started_at timestamptz,
  finished_at timestamptz
);

-- catalog_assets (EAM/CMMS)
create table catalog_assets (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  asset_tag text not null,
  modulo text,
  codigo_tecnico text,
  vigente boolean default true,
  unique (tenant_id, asset_tag)
);
```

*(Ajustar a schema Supabase existente; migración incremental, no big-bang.)*

---

## 9. Cambios implementados (2026-08-31)

| ID | Tarea | Estado |
|----|-------|--------|
| A1 | Skip Fase 0 por `file_hash` | Hecho |
| A2 | `out/ingestion-registry.json` + `ingestion_jobs` (SQL) | Hecho |
| A3 | Migración `docs/migrations/002_ingestion_v2.sql` | Hecho ✅ aplicada en Supabase |
| A4 | `ingest_file` con estados + catálogo lógico | Hecho |
| A5 | `pg_activate_document_version` atómico | Hecho |
| A6 | Filtro búsqueda `version_status=active` + `is_current` | Hecho |
| A7 | Validación `document_key`, `tipo`, `tenant` | Hecho |
| A8 | CLI `mmi.tools.reindex_clean` | Hecho |

### Comandos nuevos

```powershell
# 1. Aplicar migración en Supabase SQL Editor
#    docs/migrations/002_ingestion_v2.sql

# 2. Fase 0 idempotente (skip si hash igual)
.venv\Scripts\python -m mmi.tools.process_manifest

# 3. Indexar lote 1 (activación atómica si migración aplicada)
.venv\Scripts\python -m mmi.tools.index_lote1

# 4. Limpiar documentos fuera de lote1 + re-index opcional
.venv\Scripts\python -m mmi.tools.reindex_clean --dry-run
.venv\Scripts\python -m mmi.tools.reindex_clean --reindex

# 5. Registro local de jobs
#    out/ingestion-registry.json
```

### Modo legacy

Si la migración 002 **no** está aplicada, `ingest_file` usa `_ingest_legacy` (comportamiento anterior, `is_current=true` inmediato).

---

## 10. Criterios de éxito

- Cero re-extracción de archivos sin cambio de hash en Fase 0.
- Cero re-embed de binarios duplicados (SHA-256 igual).
- Una sola versión `active` / `is_current` por `document_key` y tenant.
- Búsqueda sin resultados de versiones `superseded` por defecto.
- Trazabilidad: de chunk a `version_id` → archivo → job de ingesta.
- Tiempo y coste por documento registrados en `ingestion_jobs.metrics`.

---

## 10. Referencias

- **Fase B (plan operativo):** `docs/plan-fase-b.md`
- Plan general MVP: `docs/plan.md`
- Manus v3: `manus308/Planificación de la Idea/`
- Código ingesta actual: `src/mmi/index/pipeline.py`, `src/mmi/tools/process_manifest.py`
