# Análisis de datos — MMi corpus ODS1/NCC30

**Rama:** `analisis-datos` (incluye Mapa E1–E4)  
**Fecha:** 2026-09-01  
**Estado:** ✅ Sprint A + B4 · 🔄 B1 parcial · ⏳ B2–B3, C, D1–D2

---

## 1. Objetivo

Explorar y documentar con datos el estado del corpus, la calidad de extracción/indexación y el rendimiento de búsqueda — sin cambiar el pipeline de ingesta.

**Preguntas guía:**

1. ¿Qué proporción del corpus está indexada, rechazada o pendiente?
2. ¿Cuántos planos hay en `02 INF TEC` y cuáles son candidatos OCR prioritarios?
3. ¿Dónde falla la recuperación (golden set / smoke) y por qué tipo documental?
4. ¿Qué gaps de cobertura hay por dominio, tipo o carpeta?

---

## 2. Fuentes de datos (artefactos `out/`)

| Artefacto | Contenido |
|-----------|-----------|
| `analysis-status.json` | Fase 0 pass/review/reject por documento |
| `index-corpus-summary.json` | Indexados, errores, duplicados |
| `plan-scan.json` | 309 PDFs INF TEC · 50 planos detectados |
| `golden-set-eval.json` | Recall@k, MRR (35 casos C3) |
| `query-smoke.json` | 3 consultas smoke (búsqueda) |
| `rag-validation.json` | 10 casos validación RAG |
| `ocr-pilot-summary.json` | Piloto OCR plano instrumentación |
| `load-test-report.html` | Latencia búsqueda/RAG (si existe) |

Corpus en disco: `ODS1 TORR ENF DCH/` · extracciones: `out/ods1-extract/`, `out/lote1-extract/`

---

## 3. Tareas propuestas

### Sprint A — Inventario y cobertura ✅

| # | Tarea | Salida | Estado |
|---|-------|--------|--------|
| A1 | Resumen Fase 0 por tipo (pdf, pptx, xlsx, docx) | tabla + gráfico | ✅ `data_report` |
| A2 | Cobertura indexación vs manifest corpus | % por carpeta raíz | ✅ |
| A3 | Distribución planos (`plan-scan.json`) por subcarpeta y confianza | ranking prioridad OCR | ✅ 50 planos |
| A4 | Documentos `reject` / `review` — causas top | lista accionable | ✅ |

### Sprint B — Calidad recuperación

| # | Tarea | Salida | Estado |
|---|-------|--------|--------|
| B1 | Desglose golden set por categoría (norma, guía, tabla, plano) | heatmap recall@5 | 🔄 en `report.json` |
| B2 | Casos con recall &lt; 1 — diagnóstico chunk/título | informe | ⏳ |
| B3 | Comparativa reranker on/off (ya en `golden-set-rerank-compare.json`) | delta MRR | ⏳ |
| B4 | Smoke + validación RAG como dashboard periódico | `out/data-quality.html` | ✅ |

### Sprint C — OCR y planos (opcional) ⏳

| # | Tarea | Salida | Estado |
|---|-------|--------|--------|
| C1 | Métricas piloto `4600027995-06950-201ME-00001` vs PDF nativo | confianza por página | 🔄 piloto en `ocr-pilot-summary.json` |
| C2 | Estimación costo/tiempo OCR 50 planos INF TEC | proyección | ⏳ |
| C3 | Tags EAM detectados en OCR vs catálogo | tasa validación | ⏳ |

### Sprint D — Entradas al Mapa de Conocimiento (Fase E)

| # | Tarea | Salida | Estado |
|---|-------|--------|--------|
| D1 | Matriz co-ocurrencia `asset_codes` × `document_key` | aristas `co_occurs` | ⏳ |
| D2 | Top pares chunk similares (Qdrant, muestra 500) | umbral similitud recomendado | ⏳ |
| D3 | Nodos concepto candidatos (FMECA modos falla, tags EAM) | `out/data-analysis/concepts.json` | 🔄 vía Mapa E4 (en grafo) |
| D4 | Informe gaps por activo/área | prioridad expansión grafo | 🔄 recomendaciones en `data-quality.html` |

Ver especificación completa: [`plan-mapa-conocimiento.md`](plan-mapa-conocimiento.md)

---

## 4. Comandos

```powershell
cd mmi-by-monitoring

# Regenerar métricas base
.venv\Scripts\python -m mmi.tools.analysis_status --skip-reviews
.venv\Scripts\python -m mmi.tools.eval_retrieval
.venv\Scripts\python -m mmi.tools.query_smoke
.venv\Scripts\python -m mmi.tools.validate_rag --search-only
.venv\Scripts\python -m mmi.tools.data_report

# Salida Fase D
# → out/data-analysis/report.json · out/data-quality.html
# → http://127.0.0.1:8773/data-quality.html (con serve_local)
```

---

## 5. Resultados actuales (`data_report`)

| Métrica | Valor |
|---------|-------|
| Fase 0 pass / reject / review | 1435 / **46** / 1 *(live `analysis-status.json`)*
| Indexados | 1274 |
| Planos INF TEC | 50 (de 309 PDFs) |
| Golden recall@5 | 35/35 |
| Golden MRR | ~0.91 |
| RAG validación | 10/10 |
| Smoke consultas | 3/3 |

**Recomendaciones automáticas** (en `data-quality.html`): revisar rejects, ampliar OCR en planos, cobertura baja en `04 MINUTAS (CP)`.

---

## 6. Entregables

- [x] `out/data-analysis/report.json` — agregados JSON
- [x] `out/data-quality.html` — dashboard Fase D
- [x] Script `mmi.tools.data_report`
- [ ] `docs/informe-analisis-datos.md` — narrativa extendida (opcional)
- [ ] Recomendaciones automáticas en pipeline CI

---

## 7. Referencias

- MVP: [`plan.md`](plan.md) · operaciones: [`plan-anexo-operaciones.md`](plan-anexo-operaciones.md)
- Fase C: `docs/plan-fase-c.md`
- Golden set: `fixtures/golden-set-retrieval.json`
- Planos: `out/plan-scan.json`
- Mapa Conocimiento: `docs/plan-mapa-conocimiento.md`
