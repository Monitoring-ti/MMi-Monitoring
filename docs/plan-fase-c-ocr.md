# Especificación OCR — extracción con incertidumbre para RAG

**Fecha:** 2026-08-31  
**Bloque:** C4 (Fase C)  
**Principio:** el OCR **no es texto plano**; es una extracción con incertidumbre que debe conservar **imagen, texto crudo, texto normalizado, estructura espacial y confianza**.

**Documento piloto lote 1:** `IFC-078` (`phase0=ocr`) — plano PDF escaneado / sin capa de texto nativo.

---

## 1. Relación con fases anteriores

| Capa | Fase A/B (hoy) | Fase C OCR |
|------|----------------|------------|
| Hash archivo | `file_hash` SHA-256 | Igual — antes de preprocesar |
| Hash contenido | `content_hash` texto normalizado | + `ocr_content_hash` por página |
| Estados versión | `received` → `active` | Activar solo si **todas** las páginas válidas pasan QA |
| Jobs | `ingestion_jobs` por etapa | + `ocr_jobs` con progreso por página |
| Extracción PDF nativa | `ingest/pdf.py` marca `needs_ocr` | Rama OCR para páginas sin texto |
| PPTX visual | `pptx_visual.py` stub | Reutiliza motor OCR por región |
| Catálogo EAM | `catalog_assets` (B4) | Validación tags en `ocr_validations` |

**No indexar** texto OCR sin página de origen, confianza y capa cruda preservada.

---

## 2. Flujo en el pipeline MMI

```
Archivo / imagen recibido
    → SHA-256 archivo (file_hash) — inmutable, antes de todo
    → detección duplicado / versión (catalog + documents)
    → preprocesamiento selectivo (rotación, recorte, contraste, DPI)
    → detección idioma, orientación, tipo documental
    → OCR por página o región
    → reconstrucción bloques / párrafos / tablas / campos + coordenadas
    → capas: crudo + normalizado + correcciones (sin reemplazar crudo)
    → validación de calidad + reglas técnicas
    → enriquecimiento metadatos (activo, módulo, vigencia)
    → chunking contextualizado (página + región + fuente)
    → embeddings + índice (solo bloques nuevos)
    → control humano si aplica
    → activación atómica (solo si controles OK)
```

Integración con cola B2 (etapas extendidas):

| Etapa `ingestion_jobs.stage` | Artefacto |
|------------------------------|-----------|
| `received` | job + document `received` |
| `preprocess` | `out/ocr-staging/{doc_id}/pages/{n}/preprocessed.png` |
| `ocr` | `ocr_pages` + `ocr_blocks` + JSON por página |
| `validate_ocr` | `ocr_validations` |
| `normalize` | texto normalizado (capa separada) |
| `chunk` | `out/staging/{doc_id}/chunks.json` |
| `embed` | vectores |
| `index` | `chunks` + `chunk_metadata` + Qdrant |
| `activate` | `status=active` |

---

## 3. Capas que deben conservarse

Nunca reemplazar el OCR crudo con texto corregido. La corrección es una **capa adicional** para auditoría.

| Capa | Persistencia | Uso |
|------|--------------|-----|
| Imagen original | blob / ruta inmutable | Auditoría, re-OCR |
| Imagen preprocesada | `ocr_pages.preprocessed_uri` | Trazabilidad del motor |
| Texto OCR crudo | `ocr_blocks.text_raw` | Fuente legal / revisión |
| Texto normalizado | `ocr_blocks.text_normalized` | Búsqueda / embed |
| Estructura espacial | `ocr_blocks` bbox + tipo | Citas región, planos |
| Confianza | página / bloque / token / celda | QA, routing humano |
| Correcciones | `ocr_validations` + diff crudo↔norm | No silenciar cambios |

```json
{
  "page_number": 3,
  "block_id": "b12",
  "text_raw": "IFC-0 78",
  "text_normalized": "IFC-078",
  "corrections": [
    {
      "field": "asset_tag",
      "raw": "IFC-0 78",
      "normalized": "IFC-078",
      "method": "catalog_lookup",
      "confidence": 0.42,
      "approved": false
    }
  ],
  "bbox": [120, 340, 280, 380],
  "confidence": 0.87
}
```

---

## 4. Metadatos mínimos por resultado

Cada página / bloque indexable:

| Campo | Destino |
|-------|---------|
| `document_id`, `version_id` | `documents.id`, `ocr_documents` |
| `page_number` | `ocr_pages` |
| Región / coordenadas | `ocr_blocks.bbox` |
| `tipo_documental` | `chunk_metadata.tipo_documental` |
| `idioma` | `ocr_pages.language` |
| `asset_tag`, `modulo`, vigencia | `chunk_metadata` + `catalog_assets` |
| Motor y versión OCR | `ocr_documents.engine` |
| Configuración | `ocr_documents.config` (jsonb) |
| Confianza global y por campo | `ocr_pages.confidence`, `ocr_blocks.confidence` |
| `processed_at` | timestamp |
| `validation_status` | `ocr_validations.status` |

---

## 5. Control de calidad

### Umbrales (configurables `.env`)

| Variable | Default | Efecto |
|----------|---------|--------|
| `MMI_OCR_MIN_PAGE_CONFIDENCE` | `0.75` | Página → `review` si menor |
| `MMI_OCR_MIN_BLOCK_CONFIDENCE` | `0.60` | Bloque excluido del embed |
| `MMI_OCR_CRITICAL_FIELD_CONFIDENCE` | `0.90` | Tags, fechas, unidades |

### Reglas

1. Confianza global **no es suficiente** — validar códigos técnicos contra `catalog_assets`.
2. Palabras críticas con baja confianza → flag en `ocr_validations`.
3. Reglas específicas: tags `XX-####`, fechas, unidades (`bar`, `°C`, `mm`).
4. Campos críticos ilegibles → `reject` o cola revisión humana; **no activar** versión.
5. El LLM **no corrige** códigos técnicos en ingesta — solo en respuesta con cita explícita.
6. Conservar diff crudo ↔ normalizado en `ocr_validations.diff`.

### Estados de validación

| Estado | Indexable | Activación |
|--------|-----------|------------|
| `pass` | Sí | Contribuye a activación |
| `review` | Parcial (solo bloques altos) | Requiere aprobación humana |
| `reject` | No | Bloquea activación |

---

## 6. Normalización (capa de búsqueda)

Aplicar **solo** en `text_normalized`; `text_raw` intacto.

- Espacios, saltos de línea, caracteres de control.
- Guiones y formatos unificados (búsqueda).
- Mantener `value_raw` y `value_normalized` por campo.
- **No** corregir números, códigos o unidades sin validación explícita.
- Separar narrativo vs tabular vs campos estructurados (`block_type`).

---

## 7. Chunking contextualizado

| Tipo documental | Estrategia |
|---------------|------------|
| Narrativo (manual, norma escaneada) | Sección / bloque semántico + página |
| Formulario | Fragmento por conjunto lógico de campos |
| Tabla OCR | Encabezados + filas + unidades; bbox en metadata |
| Plano / diagrama | Texto OCR ligado a región visual |
| Reporte mantenimiento | Grupo: activo, fecha, síntoma, diagnóstico, acción, resultado |

Cada fragmento debe incluir en el texto y en `chunk_metadata.extra`:

```
Documento: IFC-078 | Versión: REV15 | Página 3 | Región: bloque b12
Tipo: plano | Idioma: es | Activo: IFC-078
Confianza bloque: 0.87 | Motor: azure-di v4.0

[texto normalizado para búsqueda]

Fuente OCR cruda (referencia): "IFC-0 78"  [solo en vista revisión, no en embed si confianza baja]
```

Reglas:

- No mezclar páginas sin contexto explícito.
- Tablas: no partir filas sin repetir encabezados.
- Bloques `confidence < MMI_OCR_MIN_BLOCK_CONFIDENCE` → excluir del embed; conservar en DB para revisión.

Módulo objetivo: `src/mmi/index/ocr_chunking.py`

---

## 8. Eficiencia

| Técnica | Implementación |
|---------|----------------|
| Hash antes de OCR | `file_hash` en recepción |
| Hash por página | `page_content_hash` tras normalización |
| Hash contenido OCR global | `ocr_content_hash` en `documents` |
| Re-OCR incremental | Solo páginas con `page_hash` distinto |
| OCR avanzado selectivo | Segundo pase solo si `confidence < umbral` |
| Persistencia por página | Commit tras cada página (reanudable) |
| Embed incremental | Solo bloques nuevos (`block_content_hash`) |
| Métricas | `ocr_jobs.metrics`: tiempo, páginas, palabras, confianza, coste |

---

## 9. Estructura de almacenamiento

### SQL propuesto — `docs/migrations/003_ocr_schema.sql`

```sql
-- Identidad OCR del documento (1:1 con documents cuando extraction_method = ocr|hybrid)
create table if not exists ocr_documents (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    document_id     uuid not null references documents (id) on delete cascade,
    file_hash       text not null,
    ocr_content_hash text,
    source_uri      text not null,          -- imagen/PDF original inmutable
    engine          text not null,          -- azure-di | tesseract | ...
    engine_version  text,
    config          jsonb default '{}',
    language        text,
    orientation     text,
    status          text not null default 'processing'
        check (status in ('processing','validated','failed','superseded')),
    created_at      timestamptz not null default now(),
    unique (document_id)
);

create table if not exists ocr_pages (
    id              uuid primary key default gen_random_uuid(),
    ocr_document_id uuid not null references ocr_documents (id) on delete cascade,
    page_number     int not null,
    page_hash       text,
    original_uri    text,                   -- recorte o página rasterizada
    preprocessed_uri text,
    width_px        int,
    height_px       int,
    confidence      real,
    language        text,
    status          text not null default 'pending'
        check (status in ('pending','ocr_done','validated','failed','skipped')),
    metrics         jsonb default '{}',
    unique (ocr_document_id, page_number)
);

create table if not exists ocr_blocks (
    id              uuid primary key default gen_random_uuid(),
    ocr_page_id     uuid not null references ocr_pages (id) on delete cascade,
    block_index     int not null,
    block_type      text not null,          -- paragraph | line | table | field | figure
    text_raw        text not null,
    text_normalized text,
    bbox            jsonb,                  -- [x1,y1,x2,y2] normalizado 0-1 o px
    confidence      real,
    language        text,
    extra           jsonb default '{}'
);

create table if not exists ocr_tokens (
    id              uuid primary key default gen_random_uuid(),
    ocr_block_id    uuid not null references ocr_blocks (id) on delete cascade,
    token_index     int not null,
    text            text not null,
    confidence      real,
    bbox            jsonb
);

create table if not exists ocr_tables (
    id              uuid primary key default gen_random_uuid(),
    ocr_block_id    uuid not null references ocr_blocks (id) on delete cascade,
    headers         jsonb,
    rows            jsonb,
    cell_confidence jsonb,
    markdown        text
);

create table if not exists ocr_validations (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    ocr_document_id uuid references ocr_documents (id) on delete cascade,
    ocr_page_id     uuid references ocr_pages (id) on delete set null,
    ocr_block_id    uuid references ocr_blocks (id) on delete set null,
    rule            text not null,
    status          text not null
        check (status in ('pass','review','reject')),
    field_name      text,
    raw_value       text,
    normalized_value text,
    expected_value  text,
    confidence      real,
    diff            jsonb,
    reviewed_by     text,
    reviewed_at     timestamptz,
    created_at      timestamptz not null default now()
);

create table if not exists ocr_jobs (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    ocr_document_id uuid references ocr_documents (id) on delete set null,
    document_id     uuid references documents (id) on delete set null,
    stage           text not null,
    status          text not null default 'running'
        check (status in ('running','completed','failed','skipped')),
    attempt         int not null default 1,
    last_page       int,
    metrics         jsonb default '{}',
    error_message   text,
    started_at      timestamptz not null default now(),
    finished_at     timestamptz
);
```

Artefactos locales (staging):

```
out/ocr-staging/{document_id}/
  original/           # copia o referencia al binario
  pages/{n}/
    original.png
    preprocessed.png
    ocr_result.json   # backup antes de PG
  manifest.json       # file_hash, page_hashes, engine
```

---

## 10. Módulos Python (objetivo)

```
src/mmi/
  ingest/
    ocr.py                    # OcrPort — orquestador
    ocr_models.py             # OcrPage, OcrBlock, OcrTable, OcrResult
    ocr_preprocess.py         # rotación, contraste, DPI
    ocr_azure.py                # Azure Document Intelligence
    ocr_normalize.py          # capa búsqueda sin destruir crudo
    ocr_validate.py           # reglas + catalog_assets
    pdf.py                    # enrutar páginas needs_ocr → OCR
    pptx_visual.py            # regiones visuales → OCR selectivo
  index/
    ocr_chunking.py           # chunking con página/región/confianza
    ocr_store.py              # CRUD ocr_* tables
  analysis/
    ocr_status.py             # dashboard revisión humana
  tools/
    ocr_worker.py             # CLI worker por página
    ocr_review.py             # HTML diff crudo vs normalizado
```

### Proveedores (orden de implementación)

| Prioridad | Motor | Caso de uso |
|-----------|-------|-------------|
| C4.1 | **Azure Document Intelligence** | PDF escaneado, tablas, planos IFC |
| C4.2 | Tesseract (fallback local) | Dev / sin credenciales Azure |
| C4.3 | Visión LLM (solo región) | PPTX `needs_visual_analysis` — último recurso |

Variables `.env`:

```
OCR_PROVIDER=azure
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=
AZURE_DOCUMENT_INTELLIGENCE_KEY=
MMI_OCR_MIN_PAGE_CONFIDENCE=0.75
MMI_OCR_MIN_BLOCK_CONFIDENCE=0.60
MMI_OCR_CRITICAL_FIELD_CONFIDENCE=0.90
MMI_OCR_DPI=300
```

---

## 11. Tareas de implementación (C4 desglosado)

| ID | Tarea | Archivo |
|----|-------|---------|
| C4.1 | Modelos `OcrPage`, `OcrBlock`, `OcrResult` | `ingest/ocr_models.py` |
| C4.2 | Preprocesamiento selectivo | `ingest/ocr_preprocess.py` |
| C4.3 | Adapter Azure Document Intelligence | `ingest/ocr_azure.py` |
| C4.4 | Reemplazar `UnimplementedOcrAdapter` | `ingest/ocr.py` |
| C4.5 | Normalización dual raw/normalized | `ingest/ocr_normalize.py` |
| C4.6 | Validación + catálogo EAM | `ingest/ocr_validate.py` |
| C4.7 | Migración SQL `003_ocr_schema.sql` | `docs/migrations/` |
| C4.8 | Persistencia + store | `index/ocr_store.py` |
| C4.9 | PDF híbrido: nativo + OCR por página | `ingest/pdf.py`, `process_manifest` |
| C4.10 | Chunking OCR contextual | `index/ocr_chunking.py` |
| C4.11 | Worker reanudable por página | `tools/ocr_worker.py` |
| C4.12 | UI revisión diff + confianza | `tools/ocr_review.py`, `analysis/ocr_status.py` |
| C4.12b | Detección planos pre-OCR | `ingest/plan_detect.py`, `tools/plan_scan.py` |
| C4.13 | Indexar planos INF TEC (piloto) | `tools/ocr_index_pilot.py`, `index/ocr_sync.py` |
| C4.14 | PPTX visual → OCR región | `pptx_visual.py` |

### DoD C4

- [x] Extracción con capas crudo + normalizado por página (Azure adapter + staging)
- [x] Staging conserva `ocr_result.json` por página + `manifest.json`
- [x] `ocr_validations` con regla de tag técnico (local en manifest)
- [x] Chunks citan página + región + confianza (`ocr_chunking.py`)
- [x] Re-OCR incremental por `page_hash` (skip en `ocr_store.page_already_processed`)
- [ ] Versión no activa si página crítica en `reject` (gate indexación pendiente)
- [x] Dashboard diff crudo ↔ normalizado (`ocr-review.html`)
- [x] LLM no altera códigos en pipeline de ingesta (solo normaliza espacios)

---

## 12. Riesgos a evitar

| Riesgo | Mitigación |
|--------|------------|
| OCR en documento narrativo | `plan_detect` + gate en `ocr_worker` / `process_manifest` |
| Confundir IFC financiero con plano | `resolve_lote1` → `phase0=pdf` si no es plano |
| Sobrecorregir códigos por similitud semántica | Solo `catalog_lookup` con flag `approved` |
| Perder tablas al aplanar | `ocr_tables` + chunk tabular |
| Mezclar páginas sin contexto | Header fijo por chunk |
| OCR completo en cada carga | `page_hash` + skip |
| Activar con páginas incompletas | Activación atómica v2 + conteo páginas validadas |
| Borrar imagen original | `source_uri` inmutable; política retention |

---

## 13. Búsqueda y citas (post-OCR)

Formato de cita objetivo:

> IFC 078_REV15.pdf · REV15 · Página 3 · región b12 · confianza 0.87 · tag IFC-078

- Boost exacto en `text_normalized`; mostrar `text_raw` en panel revisión si confianza baja.
- Filtro `validation_status=pass` por defecto en búsqueda producción.
- Modo auditoría: incluir bloques `review` con advertencia en UI.

---

## 14. Referencias

- Plan Fase C general: `docs/plan-fase-c.md`
- Cola por etapas: B2 (`stages.py`, `ingest_worker`)
- Catálogo EAM: B4 (`catalog_assets`)
- PPTX visual selectivo: `docs/plan-pptx-extraction.md` § eficiencia
- SQL v2 base: `docs/migrations/002_ingestion_v2.sql`
- Puerto actual: `src/mmi/ingest/ocr.py` + `plan_detect.py`
