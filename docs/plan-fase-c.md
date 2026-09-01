# Fase C — Plan operativo MMI (post Fase B)

**Fecha:** 2026-09-01  
**Precondición:** Fase B completada (cola, PPTX, catálogo, dashboard)  
**Objetivo:** calidad de recuperación, extracción con incertidumbre (OCR), y detección de conflictos — sin mezclar con deuda de ingesta B.

**Estado global (2026-09-01):** C1 ✅ · C2 ✅ · C3 ✅ · C4 ✅ (piloto) · Motor MMI ✅

---

## 0. Cierre mínimo — probar consultas

Sin OCR ni batch: solo corpus ya indexado (~1274 docs).

```powershell
cd mmi-by-monitoring

# 1) Smoke test (3 consultas, solo búsqueda — sin API)
.venv\Scripts\python -m mmi.tools.query_smoke

# 2) Servidor local
.venv\Scripts\python -m mmi.tools.serve_local --port 8773
```

| URL | Uso |
|-----|-----|
| http://127.0.0.1:8773/search.html | Búsqueda híbrida (inmediata) |
| http://127.0.0.1:8773/rag.html | Respuesta + citas (OpenRouter en `.env`) |
| http://127.0.0.1:8773/motor.html | Activo + síntoma (Motor MMI) |
| http://127.0.0.1:8773/rag-validation.html | 10 casos validados |

**Consultas de prueba** (`fixtures/consultas-prueba.json`):

1. `NCC-030 criticidad mantenibilidad`
2. `FMECA modos falla sistema enfriamiento`
3. `GUIGS alcance mantenibilidad proyectos`

Validación extendida: `validate_rag --search-only` → `out/rag-validation.html`

---

## 1. Bloques Fase C

| Bloque | Nombre | Estado | Entregable principal |
|--------|--------|--------|----------------------|
| **C1** | Reranker post-filtro | ✅ | Mejor orden tras dense+BM25 |
| **C2** | Contradicciones multi-versión | ✅ | Alertas + banner en `rag.html` |
| **C3** | Golden set + eval | ✅ | `eval_retrieval` · 35 casos |
| **C4** | OCR con incertidumbre | ✅ (piloto) | [`plan-fase-c-ocr.md`](plan-fase-c-ocr.md) · `plan_detect` |
| **C5** | Cola async (opcional) | ⏳ | Redis / Supabase Realtime si volumen crece |

**Especificaciones detalladas:**

- OCR: [`docs/plan-fase-c-ocr.md`](plan-fase-c-ocr.md)
- PPTX (Fase B, prerequisito visual): [`docs/plan-pptx-extraction.md`](plan-pptx-extraction.md)
- **Motor MMI (consulta activo + síntoma):** [`docs/plan-mmi-motor.md`](plan-mmi-motor.md)

---

## 2. C4 — OCR (resumen)

| Tarea | Estado |
|-------|--------|
| C4.1 | Modelos `OcrPage`, `OcrBlock`, `OcrResult` | ✅ |
| C4.2 | Preprocesamiento selectivo (`ocr_preprocess.py`) | ✅ |
| C4.3 | Adapter Azure Document Intelligence | ✅ |
| C4.4 | Factory `get_ocr_adapter` / `extract_with_ocr` | ✅ |
| C4.5 | Normalización dual raw/normalized | ✅ |
| C4.6 | Validación + catálogo EAM (`ocr_validate.py`) | ✅ |
| C4.7 | Migración `003_ocr_schema.sql` | ✅ (SQL listo) |
| C4.8 | Staging local (`index/ocr_store.py`) | ✅ |
| C4.9 | PDF híbrido nativo + OCR (`pdf.extract_hybrid`) | ✅ |
| C4.10 | Chunking contextual (`index/ocr_chunking.py`) | ✅ |
| C4.11 | Worker CLI (`tools/ocr_worker.py`) | ✅ |
| C4.12 | UI diff crudo/normalizado (`tools/ocr_review.py`) | ✅ |
| C4.12b | Detección planos pre-OCR (`ingest/plan_detect.py`) | ✅ |
| C4.13 | Indexar planos INF TEC (piloto OCR real) | ✅ |
| C4.14 | PPTX visual → OCR región | ⏳ |

**Piloto OCR:** planos escaneados en `02 INF TEC` (no IFC-078 instructivo financiero — `phase0=pdf`).

```powershell
.venv\Scripts\python -m mmi.tools.ocr_test --check
.venv\Scripts\python -m mmi.tools.plan_scan --subdir "02 INF TEC" --plano-only --out out/plan-scan.json
.venv\Scripts\python -m mmi.tools.ocr_index_pilot   # plano piloto + sync extract + index
# → out/ocr-staging/<doc>/ocr-review.html · out/ocr-pilot-summary.json
```

Ver checklist completo en `plan-fase-c-ocr.md` §11.

---

## 3. C1 — Reranker

| Tarea | Estado |
|-------|--------|
| C1.1 | Reranker léxico post híbrido (`search/rerank.py`) | ✅ |
| C1.2 | Boost tags exactos / códigos documentales post-rerank | ✅ |
| C1.3 | Métricas en golden set (`eval_retrieval --compare-rerank`) | ✅ |

**DoD:** mejorar MRR/recall@5 vs baseline; comparativa en `out/golden-set-rerank-compare.json`.

---

## 4. C2 — Contradicciones

| Tarea | Estado |
|-------|--------|
| C2.1 | Detectar chunks `active` con mismo `document_key` y contenido conflictivo | ✅ |
| C2.2 | PPTX: diapositivas vigentes con RPN/criticidad distinta | ✅ |
| C2.3 | API `/api/ask` devuelve bloque `conflictos` para validación humana | ✅ |

**Archivos:** `src/mmi/search/conflicts.py` · `answer.py` · `rag_page.py` · `api_payloads.py`

**DoD:** conflicto real se muestra explícitamente en `/api/ask` y banner en `rag.html`; superseded en evidencia genera alerta.

---

## 5. C3 — Golden set y evaluación

| Tarea | Estado |
|-------|--------|
| C3.1 | 35 consultas anotadas por tipo (norma, guía, tabla, presentación, plano, motor) | ✅ |
| C3.2 | Script `tools/eval_retrieval.py` — recall@k, MRR | ✅ |
| C3.3 | CI opcional en PR | pendiente |

**Archivos:** `fixtures/golden-set-retrieval.json` · `src/mmi/eval/retrieval.py` · `out/golden-set-eval.html`

```powershell
.venv\Scripts\python -m mmi.tools.eval_retrieval
# → out/golden-set-eval.json · out/golden-set-eval.html
```

---

## 6. Orden de implementación (sprints)

### ✅ Cerrado — Calidad búsqueda (C1–C3)

1. C3 golden set (`golden-set-eval.html`)
2. C1 reranker (`--compare-rerank`)
3. C2 conflictos en `/api/ask` + `rag.html`

### ✅ Cerrado — Motor MMI (paralelo)

M1–M6: `motor.html`, hechos verificados, hipótesis, export, discrepancias EAM.

### ✅ Cerrado — OCR piloto (C4.13)

1. C4.1–C4.12b núcleo + Azure + staging + `plan_detect`
2. C4.13 piloto `4600027995-06950-201ME-00001` — 2 págs, conf. ~80%, 5 chunks, indexado
3. C4.14 PPTX regiones → OCR selectivo (pendiente)

### ⏳ Opcional — Escala (C5)

1. Cola async si volumen crece
2. Persistencia `ocr_*` en Supabase producción

---

## 7. Checklist Fase C

### Qué falta (resumen)

| Prioridad | Ítem |
|-----------|------|
| 🟡 | `plan_scan` corpus completo (resto de carpetas fuera de `02 INF TEC`) |
| 🟡 | Tablas `ocr_*` en Supabase (migración 003) |
| 🟡 | C4.14 PPTX visual → OCR región |
| 🟡 | C3.3 CI golden set en PR |
| 🟡 | Filtro `validation_status=pass` en búsqueda prod. |
| 🟢 | C5 cola async (opcional) |
| 🟢 | Re-OCR incremental completo en worker |

### OCR (C4)
- [x] Capas crudo + normalizado preservadas (`ocr_models`, staging)
- [x] Validación tags técnicos + confianza (`ocr_validate.py`)
- [x] Chunking con página/región/confianza (`ocr_chunking.py`)
- [x] UI diff crudo ↔ normalizado (`ocr-review.html`, solo alertas)
- [x] Gate `plan_detect` antes de OCR (`ocr_worker`, `process_manifest`)
- [x] Piloto plano INF TEC indexado (`ocr_index_pilot`, `ocr_sync`)
- [ ] Re-OCR incremental por página (store listo; worker parcial)
- [ ] Persistencia Supabase `ocr_*` tables en producción

### Búsqueda (C1–C3)
- [x] Reranker activo en `/api/search` (léxico C1, default on)
- [x] Golden set con recall documentado (`golden-set-eval.html`)
- [ ] Sin corrección silenciosa de códigos técnicos

### Gobernanza (C2)
- [x] Conflictos multi-versión visibles en respuesta (`conflictos` + banner en `rag.html`)
- [ ] Solo `validation_status=pass` en producción por defecto

---

## 8. Referencias

- Fase B: `docs/plan-fase-b.md`
- OCR detallado: `docs/plan-fase-c-ocr.md`
- PPTX: `docs/plan-pptx-extraction.md`
- Ingesta: `docs/plan-ingesta.md`
- MVP: `docs/plan.md`
