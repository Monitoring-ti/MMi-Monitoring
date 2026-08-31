# MMi by Monitoring — Plan de implementación

**Producto:** memoria técnica industrial (buscar y citar documentos).  
**Recorte MVP:** solo RAG sobre corpus NCC30. Sin agentes RCA/backlog. Sin n8n.  
**Repo:** `mmi-by-monitoring`  
**Última actualización:** 2026-08-30

---

## 1. Objetivo del MVP

Permitir a un usuario técnico:

1. **Buscar** fragmentos en el corpus con citas trazables (documento, versión, página/sección).
2. **Preguntar** y obtener una respuesta estructurada (Resumen + Detalle) con referencias `[1]`, `[2]`, etc.
3. **Revisar** la calidad de extracción antes de indexar (Fase 0 / QA).

Principios: trazabilidad, solo versiones vigentes en el lote inicial, no inventar normas ni revisiones.

---

## 2. Estado actual

### Hecho

| Área | Entregable | Ubicación |
|------|------------|-----------|
| Corpus local | 72 archivos en `00 DOCUMENTOS NCC30\` | picker árbol |
| Lote 1 MVP | 9 documentos Rev vigente (sin Rev 4/5) | `src/mmi/corpus/lote1.py` |
| Fase 0 extracción | PDF + Excel → manifest + HTML revisión | `mmi.tools.process_manifest` → `out/lote1-extract/` |
| QA por documento | pass / reject / pendiente | `out/analysis-status.html` |
| Indexación | Pipeline v2 + activación atómica + `reindex_clean` | `src/mmi/index/` · migración `002_ingestion_v2.sql` |
| Búsqueda híbrida | Dense OpenAI + BM25 (fallback denso en Windows) | `src/mmi/search/engine.py` |
| RAG respuestas | OpenRouter (`gpt-4o-mini` por defecto) | `src/mmi/search/answer.py` |
| UI búsqueda | Cards ayuda, respuesta ordenada, lazy-load opcionales | `out/search.html` |
| Servidor local | Estáticos + API | `mmi.tools.serve_local` puerto **8773** |

### API local

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/search.html` | UI principal |
| POST | `/api/search` | Fragmentos sin redactar |
| POST | `/api/ask` | Respuesta + `ask_id` (sin referencias ni fragmentos) |
| POST | `/api/ask-details` | `section: references \| evidence` bajo demanda |

### UI — comportamiento

- **Cómo buscar mejor:** grid de tarjetas con ejemplos clicables.
- **Responder con citas:** Resumen + Detalle siempre visible.
- **Referencias citadas** y **Fragmentos de evidencia:** colapsables; se cargan solo al expandir (ahorro de transferencia).
- Clic en `[n]` abre y carga referencias si hace falta.

---

## 3. Arquitectura (MVP)

```
Corpus local (00 DOCUMENTOS NCC30)
    → Fase 0: extractores PDF/Excel (+ OCR stub)
    → QA humano (analysis-status)
    → Index pipeline (chunks + embeddings)
        → Qdrant (vectores)
        → Supabase (documents, chunks, metadatos)
    → HybridSearchEngine (dense + BM25/RRF)
    → /api/ask → OpenRouter (generación con citas)
    → serve_local (UI + APIs)
```

**Variables de entorno** (`.env`, gitignored): `SUPABASE_*`, `QDRANT_*`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`.

---

## 4. Lote 1 — documentos MVP

Definido en `src/mmi/corpus/lote1.py`:

| Documento | Tipo | Fase 0 |
|-----------|------|--------|
| NCC-030 REV02 | norma | pdf |
| GUIGS-00001 Rev 6 | guía | pdf |
| PROGS-0001 | sop | pdf |
| Anexo C Checklist | tabla | excel |
| FRMGS-0035 FMECA | tabla | excel (plantilla → reject) |
| FRMGS-0036 RCM | tabla | excel |
| FMECA capacitación | presentación | **pptx pendiente** — [spec](plan-pptx-extraction.md) |
| RCM capacitación | presentación | **pptx pendiente** — [spec](plan-pptx-extraction.md) |
| IFC 078 REV15 | norma/ref | pdf |

---

## 5. Fases y checklist

### Fase 0 — Extracción y QA

- [x] Inventario corpus + picker árbol (`corpus-picker.html`)
- [x] Extractor PDF con texto nativo
- [x] Extractor Excel (headers, sheet/row, anclas)
- [x] Manifest + visor HTML por documento
- [x] Dashboard estado análisis
- [ ] Extractor **PPTX** jerárquico (FMECA/RCM) — [`docs/plan-pptx-extraction.md`](plan-pptx-extraction.md)
- [ ] OCR con incertidumbre (IFC-078 piloto) — [`docs/plan-fase-c-ocr.md`](plan-fase-c-ocr.md)
- [ ] Rechazo automático consistente para plantillas vacías (FRMGS-0035)

### Fase 1 — Indexación

- [x] Chunking + embeddings OpenAI
- [x] Pipeline Qdrant + Supabase
- [x] CLI `index_lote1`
- [x] Detección duplicados por hash SHA-256
- [ ] **Re-indexación limpia** (solo Rev 6, sin restos Rev 4/5 en Qdrant)
- [ ] Cola `ingest_jobs` (schema Manus) si se escala ingestión

### Fase 2 — Búsqueda y RAG

- [x] Motor híbrido dense + BM25
- [x] Boost seguridad / versión vigente
- [x] Respuesta estructurada con citas
- [x] Referencias ordenadas + lazy-load
- [x] UI cards + ejemplos de consulta
- [ ] BM25 estable en **Windows** (onnxruntime / VC++ Redistributable)
- [ ] Golden set / evaluación recall (Fase 6 Manus)
- [ ] Filtros UI: tipo documento, dominio, criticidad

### Fase 3 — Producto

- [ ] Auth multi-tenant (Supabase)
- [ ] Despliegue cloud (no solo `serve_local`)
- [ ] Rotación y gestión segura de claves
- [ ] Unificar código `manus308/` con `src/mmi/` o archivar referencia

---

## 6. Comandos operativos

```powershell
# Entorno
cd mmi-by-monitoring
.venv\Scripts\python -m pip install -e .

# Fase 0 — extracción lote 1
.venv\Scripts\python -m mmi.tools.process_manifest

# Estado QA
.venv\Scripts\python -m mmi.tools.analysis_status --serve

# Indexación (requiere migración 002 en Supabase)
.venv\Scripts\python -m mmi.tools.index_lote1

# Limpieza índice + re-index lote 1
.venv\Scripts\python -m mmi.tools.reindex_clean --dry-run
.venv\Scripts\python -m mmi.tools.reindex_clean --reindex

# Servidor local (usar siempre para la UI; no abrir HTML directo)
.venv\Scripts\python -m mmi.tools.serve_local --port 8773

# CLI
.venv\Scripts\python -m mmi.tools.search_cli "¿Qué es mantenibilidad?" --ask
.venv\Scripts\python -m mmi.tools.search_cli --write-html out\search.html
```

**URLs locales**

- Búsqueda: http://127.0.0.1:8773/search.html
- Estado análisis: http://127.0.0.1:8773/analysis-status.html
- Corpus: http://127.0.0.1:8773/corpus-picker.html

---

## 7. Pendientes priorizados

**Fase B** — ver `docs/plan-fase-b.md` (4 sprints).

1. **Sprint 1:** `reindex_clean --reindex` + verificación estados Supabase
2. **Sprint 2:** Cola por etapas (`stages.py` + `ingest_worker`)
3. **Sprint 3:** PPTX + `catalog_assets` + validación metadatos
4. **Sprint 4:** Chunk con contexto + `ingestion-status.html`

**Fase C** — ver `docs/plan-fase-c.md` · OCR: `docs/plan-fase-c-ocr.md`.

1. **Sprint C1:** OCR piloto IFC-078 + migración `003_ocr_schema.sql`
2. **Sprint C2:** PPTX visual + validación EAM en OCR
3. **Sprint C3:** Golden set + reranker
4. **Sprint C4:** Contradicciones + cola async (opcional)

---

## 8. Decisiones cerradas

| Tema | Decisión |
|------|----------|
| Vector DB | Qdrant Cloud |
| Metadatos | Supabase (Postgres REST) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Generación MVP | OpenRouter (`openai/gpt-4o-mini`) |
| Gemini | Descartado (clave AQ.* no habilitada para API) |
| Integración | APIs Python directas, sin n8n |
| Lote inicial | Solo revisiones vigentes Rev 6 / REV02 |

---

## 9. Riesgos conocidos

- **Servidor incorrecto en 8773** → 404 en `/api/ask`; usar siempre `serve_local`.
- **HTML vía `file://`** → APIs no disponibles; abrir vía http://127.0.0.1:8773/.
- **Sesiones `ask_id`** → expiran ~30 min; referencias/fragmentos lazy requieren misma sesión.
- **Corpus mixto en índice** → resultados pueden citar Rev antigua hasta re-indexación limpia.
- **Claves expuestas en chat** → rotar OpenAI, Supabase, Qdrant, OpenRouter.

---

## 10. Referencias

- Plan de ingesta (Fase A): `docs/plan-ingesta.md`
- **Plan Fase B:** `docs/plan-fase-b.md`
- **Plan Fase C:** `docs/plan-fase-c.md` · OCR: `docs/plan-fase-c-ocr.md`
- PPTX: `docs/plan-pptx-extraction.md`
- Plan detallado Manus (v3): `manus308/Planificación de la Idea/`
- Inventario SharePoint: `docs/sharepoint-ncc30-inventory.md`
