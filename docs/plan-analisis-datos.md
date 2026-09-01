# Análisis de datos — MMi corpus ODS1/NCC30

**Rama:** `analisis-datos`  
**Fecha:** 2026-09-01  
**Precondición:** MVP indexado (~1274 docs) · Fase C cerrada para consultas · `serve_local :8773`

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

### Sprint A — Inventario y cobertura

| # | Tarea | Salida |
|---|-------|--------|
| A1 | Resumen Fase 0 por tipo (pdf, pptx, xlsx, docx) | tabla + gráfico |
| A2 | Cobertura indexación vs manifest corpus | % por carpeta raíz |
| A3 | Distribución planos (`plan-scan.json`) por subcarpeta y confianza | ranking prioridad OCR |
| A4 | Documentos `reject` / `review` — causas top | lista accionable |

### Sprint B — Calidad recuperación

| # | Tarea | Salida |
|---|-------|--------|
| B1 | Desglose golden set por categoría (norma, guía, tabla, plano) | heatmap recall@5 |
| B2 | Casos con recall &lt; 1 — diagnóstico chunk/título | informe |
| B3 | Comparativa reranker on/off (ya en `golden-set-rerank-compare.json`) | delta MRR |
| B4 | Smoke + validación RAG como dashboard periódico | `out/data-quality.html` |

### Sprint C — OCR y planos (opcional)

| # | Tarea | Salida |
|---|-------|--------|
| C1 | Métricas piloto `4600027995-06950-201ME-00001` vs PDF nativo | confianza por página |
| C2 | Estimación costo/tiempo OCR 50 planos INF TEC | proyección |
| C3 | Tags EAM detectados en OCR vs catálogo | tasa validación |

---

## 4. Comandos

```powershell
cd mmi-by-monitoring

# Regenerar métricas base
.venv\Scripts\python -m mmi.tools.analysis_status --skip-reviews
.venv\Scripts\python -m mmi.tools.eval_retrieval
.venv\Scripts\python -m mmi.tools.query_smoke
.venv\Scripts\python -m mmi.tools.validate_rag --search-only

# Inventario planos (ya generado)
# out/plan-scan.json — 309 PDFs, 50 planos en 02 INF TEC
```

---

## 5. Entregables

- [ ] `docs/informe-analisis-datos.md` — narrativa + hallazgos
- [ ] `out/data-analysis/` — JSON/CSV agregados
- [ ] Script `mmi.tools.data_report` (opcional) — unifica fuentes `out/`
- [ ] Recomendaciones priorizadas para ingesta/OCR/index

---

## 6. Referencias

- MVP: `docs/plan.md`
- Fase C: `docs/plan-fase-c.md`
- Golden set: `fixtures/golden-set-retrieval.json`
- Planos: `out/plan-scan.json`
