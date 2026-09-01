# Matriz de compatibilidad — tipos de archivo MMI

**Actualizado:** 2026-08-31  
**Corpus local:** NCC30 + ODS1 (~1735 archivos escaneables en picker)  
**Lote 1 MVP:** 9 archivos

---

## Resumen por extensión (corpus completo)

| Ext. | Cantidad | Fase 0 | Index | Estado | Spec |
|------|----------|--------|-------|--------|------|
| `.docx` | ~20 | ✅ | ✅ | **Ready B7** | [plan-docx-extraction.md](plan-docx-extraction.md) |
| `.doc` | 0* | ⚠️ | ⚠️ | Partial (LibreOffice) | vía conversión |
| `.xlsx` | ~19 | ✅ | ✅ | Ready | — |
| `.pdf` | ~16 | ✅ | ✅ | Ready (nativo) | — |
| `.pptx` | ~9 | ✅ | ⚠️ | Ready; index lote1 pendiente | [plan-pptx-extraction.md](plan-pptx-extraction.md) |
| `.jpg` / `.png` | ~8 | ❌ | ❌ | Planned C4 | [plan-fase-c-ocr.md](plan-fase-c-ocr.md) |
| `.csv` | pocos | ❌ | ❌ | Planned | reutilizar excel |
| `.txt` / `.md` | pocos | ❌ | ❌ | Unsupported MVP | — |

\*Sin `.doc` en inventario local actual; puede aparecer en SharePoint.

---

## Lote 1 — estado detallado

| Archivo | phase0 | Fase 0 | Index | Notas |
|---------|--------|--------|-------|-------|
| NCC-030 PDF | pdf | ✅ pass | duplicado | 45 págs |
| GUIGS Rev 6 PDF | pdf | ✅ pass | duplicado | 68 págs |
| PROGS SOP PDF | pdf | ✅ pass | duplicado | 58 págs |
| Anexo C xlsx | excel | ✅ pass | error onnx | 118 filas |
| FRMGS-0035 xlsx | excel | ❌ reject | — | plantilla vacía |
| FRMGS-0036 xlsx | excel | ✅ pass | duplicado | 1 fila |
| FMECA pptx | pptx | ✅ pass 51/51 | **pendiente** | extracción OK |
| RCM pptx | pptx | ✅ pass 62/62 | **pendiente** | extracción OK |
| IFC-078 PDF | ocr | ✅ pass 98% | duplicado | Azure 61 págs |

---

## Integración código (2026-08-31)

| Módulo | PDF | Excel | PPTX | OCR | DOCX |
|--------|-----|-------|------|-----|------|
| `process_manifest` | ✅ | ✅ | ✅ | ✅ | ✅ `--docx-only` |
| `ingest/*` | pdf.py | excel.py | pptx.py | ocr_azure.py | docx.py |
| `blocks_from_path` | ✅ | ✅ | ✅ | vía ocr cache | ✅ |
| `chunk_blocks` | pdf | xlsx | pptx | pdf* | docx |
| `corpus_picker` | ✅ | ✅ | ✅ | — | ✅ + filtros |
| `lote1.py` | ✅ | ✅ | ✅ | ✅ | ❌ (fuera lote 1) |

\* OCR usa bloques con contexto página/confianza.

---

## Selector corpus (nuevo)

| Función | Estado |
|---------|--------|
| Filtro tipo (extensión) | ✅ dinámico |
| Filtro ubicación (carpeta raíz) | ✅ |
| Filtro fuente / estado procesado | ✅ |
| Orden nombre / tamaño | ✅ |
| Checkbox sí/no análisis | ✅ → `include_in_analysis` |
| Muestra ya procesados (Fase 0) | ✅ verde + badge |

---

## Gaps prioritarios (actualizado)

### Crítico

1. **Index PPTX lote 1** — extracción OK, falta `index_lote1`
2. **Re-index limpio** — posibles restos Rev 4/5 en Qdrant
3. **Anexo C index** — error onnxruntime Windows

### Alto

4. **~20 DOCX sin Fase 0 masiva** — código listo, falta `--docx-only`
5. **Cola B2** — pipeline monolítico, sin reanudación por etapa
6. **Dashboard ingesta B6** — jobs/versiones sin HTML

### Medio

7. Imágenes JPG/PNG → OCR selectivo (C4)
8. Golden set evaluación (C3)
9. BM25 estable Windows

---

## Comandos por tipo

```powershell
.venv\Scripts\python -m mmi.tools.process_manifest              # lote 1
.venv\Scripts\python -m mmi.tools.process_manifest --pptx-only
.venv\Scripts\python -m mmi.tools.process_manifest --ocr-only
.venv\Scripts\python -m mmi.tools.process_manifest --docx-only
.venv\Scripts\python -m mmi.tools.corpus_picker --serve
.venv\Scripts\python -m mmi.tools.file_types_report --corpus "00 DOCUMENTOS NCC30"
```
