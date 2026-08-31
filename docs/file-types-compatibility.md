# Matriz de compatibilidad — tipos de archivo MMI

**Actualizado:** 2026-08-31  
**Corpus local:** `00 DOCUMENTOS NCC30` (~72 archivos)  
**Lote 1 MVP:** 9 archivos (sin DOCX)

---

## Resumen por extensión (corpus completo)

| Ext. | Cantidad | Fase 0 | Index | Estado | Spec |
|------|----------|--------|-------|--------|------|
| `.docx` | ~20 | ❌ | ❌ | **Planned B7** | [plan-docx-extraction.md](plan-docx-extraction.md) |
| `.doc` | 0* | ❌ | ❌ | Planned B7 | vía conversión |
| `.xlsx` | ~19 | ✅ | ✅ | Ready | — |
| `.pdf` | ~16 | ✅ | ✅ | Ready (nativo) | — |
| `.pptx` | ~9 | ✅ | ⚠️ parcial | Ready B3 | [plan-pptx-extraction.md](plan-pptx-extraction.md) |
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
| FMECA pptx | pptx | ✅ pass | **pendiente** | 51 slides |
| RCM pptx | pptx | ✅ pass | **pendiente** | 62 slides |
| IFC-078 PDF | ocr | ✅ pass 98% | duplicado | 61 págs Azure |

---

## Integración código (hoy)

| Módulo | PDF | Excel | PPTX | OCR | DOCX |
|--------|-----|-------|------|-----|------|
| `process_manifest` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `ingest/*` | pdf.py | excel.py | pptx.py | ocr_azure.py | ❌ |
| `blocks_from_path` | ✅ | ✅ | ✅ | vía pdf+ocr | ❌ raise |
| `chunk_blocks` | pdf | xlsx | pptx | pdf* | **pdf† bug** |
| `store EXT_METHOD` | native | tabular | slide | ocr | native‡ |
| `corpus_picker PROCESSABLE` | ✅ | ✅ | ✅ | — | ✅‡ UI only |
| `lote1.py` | ✅ | ✅ | ✅ | ✅ | ❌ |

\* OCR usa bloques con contexto página/confianza.  
† `chunking.py` línea `if fmt in {".pdf", ".docx"}` — **incorrecto** hasta B7.  
‡ Marcado procesable pero sin extractor.

---

## DOCX en corpus (fuera lote 1) — ejemplos

| Archivo | Ruta relativa | Prioridad sugerida |
|---------|---------------|-------------------|
| Anexos GUIGS rev 4 | `1. NORMA/Anexos … rev 4.docx` | **Piloto B7** (complementa guía) |
| FRMGS-0013 … 0015 | `3. REFERENCIA ANEXOS/…/SGPD-07MYC-FRMGS-001x.docx` | Formularios — tablas |
| Otros ~17 docx | VARIOS / ANEXOS | Lote 2 post-B7 |

---

## Gaps prioritarios

### Crítico (rompe o engaña al usuario)

1. **DOCX en picker como “procesable”** pero sin Fase 0 → confusión.
2. **`chunking.py` enruta docx a PDF** → fallaría silenciosamente o con error críptico.
3. **PPTX indexación pendiente** — extracción OK, falta `index_lote1`.
4. **Anexo C index** — error onnxruntime Windows (BM25); denso debería funcionar.

### Alto (corpus bloqueado)

5. **B7 extractor DOCX** — 20 archivos (~28% del corpus).
6. **`.doc` legacy** — conversión antes de extracción.
7. **Imágenes sueltas** — diagramas JPG/PNG sin pipeline.

### Medio (Fase B/C)

8. Cola por etapas B2 — reanudación docx/pptx/ocr.
9. SQL `003_ocr` / `004_docx` — capas en Postgres.
10. `.csv` — adapter trivial vía pandas/openpyxl.

---

## Comando — reporte en vivo

```powershell
.venv\Scripts\python -m mmi.tools.file_types_report
.venv\Scripts\python -m mmi.tools.file_types_report --corpus "00 DOCUMENTOS NCC30"
```

Genera `out/file-types-report.json` con conteos por extensión y compatibilidad.

---

## Roadmap tipos

```
Hoy     PDF Excel PPTX OCR(Azure)
B7      + DOCX (+ DOC convert)
B2      Cola reanudable todos
C4      JPG/PNG/TIFF + tablas OCR
Lote 2  + ~20 docx + LIBRO SOMA OCR
```

---

## Referencias

- DOC/DOCX spec: [plan-docx-extraction.md](plan-docx-extraction.md)
- Registro código: `src/mmi/ingest/file_types.py`
- Fase B: [plan-fase-b.md](plan-fase-b.md)
