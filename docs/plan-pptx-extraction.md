# Especificación PPTX — extracción jerárquica para RAG

**Fecha:** 2026-08-31  
**Bloque:** B3 (Fase B)  
**Documentos lote 1:** `fmeca-capacitacion`, `rcm-capacitacion`  
**Principio:** el PPTX **no es texto continuo**; es una jerarquía **presentación → sección → diapositiva → elemento → fragmento**.

---

## 1. Flujo en el pipeline MMI

```
PPTX recibido
    → SHA-256 archivo (file_hash)
    → extracción por diapositiva (Fase 0)
    → representación intermedia (slides.json)
    → validación + QA
    → normalización contextual (texto para chunking)
    → chunking semántico
    → embeddings + índice (PG + Qdrant)
    → control de calidad
    → activación atómica (solo si todas las slides válidas indexadas)
```

**No** enviar el PPTX ni markdown crudo directamente al embedder. Siempre pasar por la representación intermedia y la capa de texto contextualizado.

Integración con cola B2:

| Etapa `ingestion_jobs.stage` | Artefacto |
|------------------------------|-----------|
| `extract` | `out/lote1-extract/{slug}/slides.json` + `extracted.json` (resumen) |
| `validate` | reglas QA + metadatos obligatorios |
| `chunk` | `out/staging/{doc_id}/chunks.json` |
| `embed` | vectores (opcional en disco) |
| `index` | `chunks` + `chunk_metadata` + Qdrant |
| `activate` | `status=active`, versión anterior → `superseded` |

---

## 2. Extracción por diapositiva

Por cada slide, en **orden visual** (top→bottom, left→right dentro de cada fila del layout):

| Elemento | Qué extraer |
|----------|-------------|
| Identidad | Número de diapositiva, título (placeholder o primer heading) |
| Cuadros de texto | Texto de cada shape, respetando orden visual |
| Notas | Speaker notes completas |
| Tablas | Markdown tabular estructurado (encabezados repetibles) |
| Gráficos | Título, ejes, leyenda, series y valores disponibles (vía `python-pptx` chart API) |
| Imágenes / diagramas / SmartArt | Referencia visual (`media_ref`); descripción solo si aporta información no presente en texto |
| Layout maestro | Encabezado, pie, sección y diseño maestro **solo si** aportan contexto (ej. nombre de módulo en master) |

### Eficiencia (fase extract)

1. **Primero:** texto, tablas, notas, metadatos de gráfico (sin render).
2. **Después (selectivo):** OCR o análisis visual solo si `extraction_quality` indica slide “solo visual” o gráfico sin datos serializados.
3. Guardar resultado **antes** de embeddings.
4. Reanudar desde la diapositiva fallida (`ingestion_jobs.metrics.last_slide`).

---

## 3. Representación intermedia

Archivo principal: `slides.json` (array ordenado). Esquema por diapositiva:

```json
{
  "presentation_id": "uuid-catalog",
  "version_id": "uuid-document",
  "slide_number": 12,
  "slide_title": "Análisis de modos de falla",
  "section_title": "FMECA — Metodología",
  "elements": [
    {
      "kind": "text_box",
      "order": 0,
      "text": "...",
      "bbox": [x, y, w, h]
    },
    {
      "kind": "table",
      "order": 1,
      "headers": ["Modo", "Efecto", "Criticidad"],
      "rows": [["...", "...", "..."]],
      "markdown": "| Modo | Efecto | ..."
    },
    {
      "kind": "chart",
      "order": 2,
      "title": "Distribución RPN",
      "axes": {"x": "...", "y": "..."},
      "legend": ["..."],
      "series": [{"name": "...", "values": [1, 2, 3]}]
    },
    {
      "kind": "image",
      "order": 3,
      "media_ref": "slide_12_img_0.png",
      "description": null,
      "needs_visual_analysis": true
    }
  ],
  "speaker_notes": "...",
  "visual_summary": "Diagrama de flujo FMECA con 5 pasos",
  "source_location": {
    "file": "FMECA MONITORING 092021 rev 1.pptx",
    "slide": 12,
    "document_key": "fmeca-capacitacion"
  },
  "slide_content_hash": "sha256-normalizado",
  "extraction_quality": "pass"
}
```

### Campos `extraction_quality`

| Valor | Criterio |
|-------|----------|
| `pass` | ≥1 elemento con texto útil o tabla/gráfico con datos |
| `review` | Solo imagen sin descripción; notas vacías; título genérico |
| `reject` | Slide vacía (sin texto, tabla, notas ni descripción) |

`extracted.json` (compatible con Fase 0 existente) incluye: `file_hash`, `slide_count`, `quality` agregado, ruta a `slides.json`, métricas por slide.

### Tipos Python (objetivo)

```
src/mmi/ingest/pptx_models.py   # SlideRecord, SlideElement, PresentationExtract
src/mmi/ingest/pptx.py          # PptxAdapter.extract() → PresentationExtract
src/mmi/ingest/ports.py         # PresentationPort (ABC)
```

---

## 4. Texto contextualizado para RAG

Función: `slides_to_context_blocks(slides, catalog_meta) → list[ContextBlock]`.

Cada bloque de texto **antes del chunking** debe poder leerse así:

```
Presentación: FMECA MONITORING | Versión: Rev 1
Sección: FMECA — Metodología
Diapositiva 12: Análisis de modos de falla

[Contexto anterior: slide 11 resume el objetivo del análisis…]  (opcional)

Contenido:
…texto y bullets…

Tablas:
| Modo | Efecto | Criticidad |
…

Descripción visual:
Diagrama de flujo FMECA con 5 pasos…

Metadatos: activo=NCC30 | módulo=Capacitación | tipo=presentación | vigencia=…
```

Reglas:

- El **título de la diapositiva se repite** en cada fragmento derivado de esa slide.
- **No dividir** una tabla, una secuencia de pasos ni una explicación visual sin conservar referencia (slide + elemento).
- Contexto anterior/posterior: incluir solo en slides densas o cuando el chunking parta una slide en varios bloques.

---

## 5. Chunking

Estrategia en `src/mmi/index/pptx_chunking.py` (o rama en `chunking.py` para `tipo=presentacion`):

| Caso | Regla |
|------|-------|
| Slide simple | 1 fragmento = 1 diapositiva |
| Slide densa | Dividir por bloques semánticos (`elements`); cada fragmento lleva `slide_number` + `slide_title` |
| Tabla | 1 fragmento por tabla, o por grupo de filas con **encabezados repetidos** |
| Diagrama | 1 fragmento con descripción de relaciones, componentes y flujo |
| Presentación técnica | Fragmentos adicionales **agrupados por `section_title`** (consultas multi-slide) |
| Solo visual | No indexar si no hay texto ni `visual_summary` verificable → `review` / skip embed |

Objetivo de tamaño: 400–500 tokens por fragmento slide; secciones agrupadas hasta ~800 tokens.

### Mapeo a `Block` existente

```python
Block(
    text=contextualized_text,
    slide=slide_number,
    notes=speaker_notes,
    meta={
        "slide_title": "...",
        "section_title": "...",
        "element_kinds": ["text_box", "table"],
        "slide_content_hash": "...",
        "source_element_orders": [0, 1],
    },
)
```

Payload Qdrant / `chunk_metadata.extra`:

- `slide_number`, `slide_title`, `section_title`
- `presentation_id`, `document_key`, `version_label`
- `element_kind`, `media_ref` (si aplica)

---

## 6. Control de duplicados y versiones

| Nivel | Hash | Uso |
|-------|------|-----|
| Archivo | SHA-256 binario (`file_hash`) | Skip Fase 0 completo si igual |
| Contenido global | `content_hash` (texto normalizado de toda la presentación) | Skip embed si solo cambió metadata |
| Diapositiva | `slide_content_hash` (texto+tablas+notas normalizados) | Reprocesar **solo slides modificadas** |

Comportamiento:

1. Mantener copia del PPTX original (ruta en `documents.source_path`) para auditoría.
2. Nueva versión: indexar slides nuevas/modificadas; las no tocadas reutilizan chunks si `slide_content_hash` coincide.
3. **Activación:** solo cuando todas las slides con `quality != reject` están indexadas.
4. Versión anterior: chunks → `superseded` en documento; puntos Qdrant con `version_status=superseded` (no borrar).

Métricas por slide en `ingestion_jobs.metrics.slides[]`:

```json
{"slide": 12, "ms": 340, "elements": 4, "tokens_est": 180, "quality": "pass", "errors": []}
```

---

## 7. Búsqueda y citas

Hooks en Fase B (filtros); refinamiento en Fase C:

| Capacidad | Fase | Implementación |
|-----------|------|----------------|
| Filtrar tenant, activo, módulo, tipo, vigencia | B | `chunk_metadata` + payload Qdrant |
| Boost tags / códigos exactos | B | engine existente + `asset_tag` |
| Recuperar slide → contexto de sección | B | payload `section_title`; chunks sección |
| Cita: presentación + versión + slide + elemento | B | `answer.py` + anchors |
| Diapositivas contradictorias entre versiones | C | detección multi-versión, no en B3 |

Formato de cita objetivo:

> FMECA MONITORING 092021 rev 1.pptx · Rev 1 · Diapositiva 12 «Análisis de modos de falla» · tabla

---

## 8. Tareas de implementación (B3 desglosado)

| ID | Tarea | Archivo |
|----|-------|---------|
| B3.1 | Modelos `SlideRecord`, `SlideElement`, `PresentationExtract` | `ingest/pptx_models.py` |
| B3.2 | Extractor: texto ordenado, notas, tablas, charts básicos | `ingest/pptx.py` |
| B3.3 | `PresentationPort` en `ports.py` | `ingest/ports.py` |
| B3.4 | Persistencia `slides.json` + `extracted.json` | `tools/process_manifest.py` |
| B3.5 | `slides_to_context_blocks()` | `ingest/pptx_normalize.py` |
| B3.6 | Chunking presentación + chunks por sección | `index/pptx_chunking.py` |
| B3.7 | `blocks_from_path` rama `.pptx` | `index/blocks.py` |
| B3.8 | `slide_content_hash` + diff incremental | `index/content_hash.py` |
| B3.9 | Análisis visual selectivo (stub → Fase C OCR) | `ingest/pptx_visual.py` |
| B3.10 | QA en `analysis/status.py` | `analysis/status.py` |
| B3.11 | Indexar FMECA + RCM; verificar búsqueda | `tools/index_lote1.py` |

### Dependencias

- `python-pptx` (extracción nativa)
- Opcional Fase C: visión/OCR para slides `needs_visual_analysis=true`

### DoD B3

- [ ] `process_manifest` procesa los 2 PPTX lote 1 sin pendientes
- [ ] `slides.json` con estructura completa por slide
- [ ] Chunks citan diapositiva + título + sección
- [ ] Tablas no partidas sin encabezado
- [ ] Re-index incremental: cambiar 1 slide no re-embede las demás
- [ ] `analysis-status` → `quality=pass` para ambos archivos
- [ ] Búsqueda «FMECA RPN» / «RCM criticidad» devuelve hits con cita slide

---

## 9. Referencias

- Plan Fase B: `docs/plan-fase-b.md` (bloque B3)
- Cola por etapas: B2 (`stages.py`, `ingest_worker`)
- Chunking contexto general: B5 (prefijos documento/versión)
- Metadatos activo/módulo: B4 (`chunk_metadata`)
- SQL v2: `docs/migrations/002_ingestion_v2.sql`
- Fase C OCR: `docs/plan-fase-c-ocr.md`
