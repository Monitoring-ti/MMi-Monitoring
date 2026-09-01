# Anexo operativo — MMi

Comandos extendidos, URLs locales y validación lote 1. Plan principal: [`plan.md`](plan.md).

**Precondiciones (todas las sesiones):**

1. Directorio: `cd mmi-by-monitoring`
2. Entorno: `.venv\Scripts\activate` (o prefijo `.venv\Scripts\python`)
3. Dependencias: `pip install -e .`
4. Variables: `.env` con `SUPABASE_*`, `QDRANT_*`, `OPENAI_API_KEY`, `OPENROUTER_*`
5. UI con API: `serve_local --port 8773` (no `file://`)
6. Health check antes de pruebas: `curl http://127.0.0.1:8773/api/graph/health` o abrir `review.html`

---

## Comandos extendidos

```powershell
# Instalación
.venv\Scripts\python -m pip install -e .

# Selector corpus
.venv\Scripts\python -m mmi.tools.corpus_picker --serve          # :8770
.venv\Scripts\python -m mmi.tools.corpus_picker --write-html out\corpus-picker.html

# Fase 0 — filtros
.venv\Scripts\python -m mmi.tools.process_manifest --write-only
.venv\Scripts\python -m mmi.tools.process_manifest --limit 50
.venv\Scripts\python -m mmi.tools.process_manifest --lote1
.venv\Scripts\python -m mmi.tools.process_manifest --pdf-only
.venv\Scripts\python -m mmi.tools.process_manifest --pptx-only
.venv\Scripts\python -m mmi.tools.process_manifest --docx-only

# Indexación
.venv\Scripts\python -m mmi.tools.ingest_worker --limit 5
.venv\Scripts\python -m mmi.tools.index_corpus --limit 20
.venv\Scripts\python -m mmi.tools.index_lote1

# OCR / planos
.venv\Scripts\python -m mmi.tools.plan_scan --subdir "02 INF TEC" --plano-only --out out\plan-scan.json
.venv\Scripts\python -m mmi.tools.ocr_index_pilot
.venv\Scripts\python -m mmi.tools.ocr_worker --ifc

# Calidad y análisis
.venv\Scripts\python -m mmi.tools.eval_retrieval --compare-rerank
.venv\Scripts\python -m mmi.tools.data_report

# Carga
.venv\Scripts\python -m mmi.tools.load_test --requests 30 --concurrency 4
.venv\Scripts\python -m mmi.tools.load_test --requests 20 --http --extract
.venv\Scripts\python -m mmi.tools.load_test --requests 12 --http --ask

# Reporte tipos
.venv\Scripts\python -m mmi.tools.file_types_report --corpus "ODS1 TORR ENF DCH/00 DOCUMENTOS NCC30"
```

---

## URLs locales (`serve_local :8773`)

| Página | URL |
|--------|-----|
| Búsqueda | http://127.0.0.1:8773/search.html |
| Consulta RAG | http://127.0.0.1:8773/rag.html |
| Mapa conocimiento | http://127.0.0.1:8773/mapa.html |
| Motor MMI | http://127.0.0.1:8773/motor.html |
| Análisis datos | http://127.0.0.1:8773/data-quality.html |
| Revisión (hub) | http://127.0.0.1:8773/review.html |
| Identidad dudosa | http://127.0.0.1:8773/review.html?index=needs_review |
| Validación RAG | http://127.0.0.1:8773/rag-validation.html |
| Corpus (estático) | http://127.0.0.1:8773/corpus-picker.html |
| Reporte carga | http://127.0.0.1:8773/load-test-report.html |

### API local

| Método | Ruta |
|--------|------|
| POST | `/api/search`, `/api/ask` |
| POST | `/api/motor/analyze`, `/api/motor/details` |
| POST | `/api/graph/search`, `/api/graph/expand`, `/api/graph/ask` |
| GET | `/api/graph/health`, `/api/graph/filters`, `/api/graph/node/{id}` |
| GET/POST | `/api/ingestion-action`, `/api/ingestion-live`, `/api/remote-source` |

---

## Lote 1 — validación

Conjunto mínimo para validar extractores y recuperación (`src/mmi/corpus/lote1.py`).  
Comando: `process_manifest --lote1`

| Documento | `logical_key` | Versión activa | Fase 0 | Estado índice | Motivo / acción pendiente |
|-----------|---------------|----------------|--------|---------------|---------------------------|
| NCC-030 REV02 | `NCC-030` | REV02 | pass | `skipped_exact_duplicate` | Ya en corpus ODS1; validar tras `reindex_clean` |
| GUIGS-00001 | `SGP-07MYC-GUIGS-00001` | Rev 6 | pass | `skipped_exact_duplicate` | — |
| PROGS-0001 | `SGPD-07MYC-PROGS-0001` | vigente | pass | `skipped_exact_duplicate` | — |
| Anexo C Checklist | `SGP-07MYC-GUIGS-00001-Anexo-C` | checklist | pass | `error` | Error onnx; reintentar indexación |
| FRMGS-0035 FMECA | `SGPD-07MYC-FRMGS-0035` | FMECA | **reject** | — | Plantilla vacía; revisión manual |
| FRMGS-0036 RCM | `SGPD-07MYC-FRMGS-0036` | RCM | pass | `skipped_exact_duplicate` | — |
| FMECA capacitación | `FMECA-CAPACITACION` | rev 1 | pass | **indexed** | Referencia PPTX OK |
| RCM capacitación | `RCM-CAPACITACION` | rev 4 | pass | **indexed** | Referencia PPTX OK |
| IFC 078 REV15 | `IFC-078` | REV15 | pass | `skipped_exact_duplicate` | PDF nativo (no plano) |

**Resumen:** 8 pass · 1 reject · 2 indexed en lote piloto · resto absorbido por batch ODS1.
