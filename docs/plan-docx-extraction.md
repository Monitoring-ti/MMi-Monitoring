# Especificación DOC/DOCX — extracción jerárquica para RAG

**Fecha:** 2026-08-31  
**Bloque:** B7 (Fase B) / extensión C4 (Azure DI compartido con OCR)  
**Principio:** DOC/DOCX **no son texto plano**; jerarquía **documento → sección → bloque → tabla/elemento → fragmento**.

**Corpus NCC30:** ~20 archivos `.docx` (anexos, formularios FRMGS, guías en Word). Sin `.doc` detectados en lote local.

---

## 1. Estado actual vs objetivo

| Capa | Hoy | Objetivo B7 |
|------|-----|-------------|
| `corpus_picker` | `.docx` marcado procesable | Igual + `phase0=docx` |
| `process_manifest` | No incluye docx | Rama `phase0=docx` → `blocks.json` |
| `chunking.py` | **Bug:** `.docx` usa `chunk_pdf_blocks` | `chunk_docx_blocks` |
| `blocks_from_path` | No soporta docx | Carga `blocks.json` cacheado |
| Indexación | Fallaría si se intenta | Tras Fase 0 pass |

---

## 2. Flujo en el pipeline MMI

```
DOC/DOCX recibido
    → SHA-256 (file_hash)
    → detección formato / duplicado
    → [.doc] conversión a DOCX común (LibreOffice headless) — original inmutable
    → extracción estructural (python-docx + opcional Azure DI layout)
    → blocks.json (representación intermedia)
    → validación tablas / secciones / SOP
    → normalización (text_raw + text_normalized)
    → chunking contextualizado
    → embeddings + índice
    → activación atómica
```

Integración cola B2:

| Etapa | Artefacto |
|-------|-----------|
| `extract` | `out/.../blocks.json` + `extracted.json` |
| `validate` | `document_validations` (local JSON hasta SQL) |
| `chunk` | chunks con sección + block_id |
| `activate` | solo si todos los bloques válidos indexados |

---

## 3. Elementos a conservar

| Elemento | Extracción |
|----------|------------|
| Títulos / heading levels | `style.name` Heading 1–9 → `level` |
| Sección / numeración | Inferida de headings + outline |
| Párrafos | `paragraph` con estilo |
| Listas | `list` con `level` y `ordered` |
| Tablas | `table` → headers, rows, markdown |
| Imágenes | `image` + `media_ref`; OCR selectivo |
| Notas al pie / finales | `footnote` / `endnote` |
| Encabezado / pie / nº página | `header` / `footer` si aportan contexto |
| Hipervínculos | `reference` con URL en `extra` |
| Comentarios / track changes | `comment` — **no mezclar** con vigente salvo regla explícita |

---

## 4. Representación intermedia (`blocks.json`)

```json
{
  "document_id": null,
  "version_id": null,
  "block_index": 42,
  "block_type": "heading",
  "level": 2,
  "section_path": "3. Mantenibilidad | 3.2 Criticidad",
  "page_or_position": 12,
  "text_raw": "3.2 Criticidad de activos",
  "text_normalized": "3.2 criticidad de activos",
  "table_id": null,
  "media_ref": null,
  "extraction_quality": "pass",
  "extra": {}
}
```

Tipos: `heading`, `paragraph`, `list`, `table`, `image`, `footnote`, `reference`, `comment`.

Hash por bloque: `block_content_hash` (texto normalizado + tipo + tabla serializada).

---

## 5. Chunking

| Tipo documental | Regla |
|---------------|-------|
| SOP / procedimiento | 1 fragmento = procedimiento completo (objetivo + precondiciones + pasos + advertencias) |
| Manual / guía Word | Por capítulo/subsección; **título repetido** en cada chunk |
| Listas | Encabezado + ítems; no partir jerarquía |
| Tablas | Encabezados repetidos; no separar de sección |
| Informes | Grupo: problema, activo, fecha, análisis, acción, resultado |
| Denso | Bloques semánticos + ventana de contexto entre secciones adyacentes |

Módulo: `src/mmi/index/docx_chunking.py`  
Reutiliza reglas SOP de `chunking.py` (`_SAFETY_RE`).

Texto contextualizado (embed):

```
Documento: Anexos GUIGS-00001 | Versión: rev 4
Sección: 3.2 Criticidad de activos
Tipo: guia | Clave: SGP-07MYC-GUIGS-00001-Anexos

Contenido:
…

Tablas:
| … |

Notas al pie:
…
```

---

## 6. Normalización

- Capa búsqueda: espacios, saltos, guiones unificados.
- **Preservar** códigos, tags, fechas, unidades en `text_raw`.
- Validar tags vs `catalog_assets` (B4).
- Comentarios/track changes: capa separada; no embed por defecto.

---

## 7. Tablas e imágenes

- Tablas: markdown estructurado; fragmento por tabla o grupo de filas.
- Imágenes decorativas: skip embed.
- Imágenes técnicas: OCR Azure selectivo → `document_media` / `extra.ocr_text`.

---

## 8. Eficiencia

- `file_hash` + `block_content_hash`
- Re-embed solo bloques modificados
- Persistir `blocks.json` antes de embeddings
- Reanudación por sección (`ingestion_jobs.metrics.last_block`)

---

## 9. Almacenamiento

**Fase B (local):** `blocks.json`, `extracted.json`, `ocr/` en staging.

**Fase C+ (SQL propuesto — `004_docx_schema.sql`):**

- `document_blocks`, `document_tables`, `document_media`
- Reutiliza `documents`, `ingestion_jobs`, `chunks`, `chunk_metadata`

---

## 10. Implementación (B7)

| ID | Tarea | Archivo |
|----|-------|---------|
| B7.1 | Modelos `DocBlock`, `DocTable`, `DocumentExtract` | `ingest/docx_models.py` |
| B7.2 | Extractor DOCX (`python-docx`) | `ingest/docx.py` |
| B7.3 | Conversión DOC→DOCX | `ingest/doc_convert.py` (LibreOffice) |
| B7.4 | Normalización dual raw/norm | `ingest/docx_normalize.py` |
| B7.5 | Azure DI fallback layout | reutilizar `ocr_azure.py` modo layout |
| B7.6 | `process_manifest --docx-only` | `tools/process_manifest.py` |
| B7.7 | `docx_chunking.py` | `index/docx_chunking.py` |
| B7.8 | Corregir `chunking.py` (quitar ruta PDF para docx) | `index/chunking.py` |
| B7.9 | QA + review HTML por sección | `analysis/status.py` |
| B7.10 | Piloto: `Anexos SGP-07MYC-GUIGS-00001 rev 4.docx` | lote 2 propuesto |

### Dependencias

- `python-docx>=1.1`
- Opcional: LibreOffice (`soffice`) para `.doc`
- Opcional: Azure DI `prebuilt-layout` para tablas complejas

### DoD B7

- [ ] 0 archivos docx en picker sin Fase 0 o marcados `planned`
- [ ] Piloto anexo Word extraído con headings + tablas
- [ ] Chunks citan sección + block_type
- [ ] SOP no partido entre precondiciones y pasos
- [ ] `chunking.py` no enruta docx a PDF

---

## 11. Referencias

- Matriz tipos: `docs/file-types-compatibility.md`
- PPTX (patrón similar): `docs/plan-pptx-extraction.md`
- OCR/tablas complejas: `docs/plan-fase-c-ocr.md`
- Plan Fase B: `docs/plan-fase-b.md`
