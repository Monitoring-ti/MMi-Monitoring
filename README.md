# MMi by Monitoring

Memoria técnica de activos: RAG de documentos con citas verificables (página OCR u hoja/fila de Excel).

Producto de [Monitoring](https://). Stack: APIs propias (sin n8n), Supabase/pgvector, embeddings y generación con retención cero contractual.

## Qué hay en este repo

| Ruta | Rol |
| --- | --- |
| `src/mmi/ingest/excel.py` | Adaptador Excel → registros + Markdown con ancla `sheet`/`row` |
| `src/mmi/ingest/ocr.py` | Puerto OCR (PDF imagen) → Markdown paginado + confianza |
| `src/mmi/ingest/ports.py` | Contratos de storage, OCR y spreadsheet |
| `fixtures/` | PDFs y XLSX de ejemplo (no datos de planta) |
| `docs/plan.md` | Recorte de producto (Fase 0 prep + desarrollo en paralelo) |

## Arranque

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Copiar `.env.example` a `.env`. No commitear secretos.

## Ver extracción de Excel

```bash
.venv\Scripts\python -m mmi.tools.preview_excel fixtures\listas-clasificacion-concentradora.xlsx --out out\excel-preview
```

Genera `extracted.html` (tablas por hoja + filtro), `extracted.json` (todas las filas con ancla sheet/row) y `extracted.md`. Para abrirlo en el navegador:

```bash
.venv\Scripts\python -m http.server 8765 --directory out\excel-preview
```

Luego visita `http://127.0.0.1:8765/extracted.html`.

## Revisar y seleccionar qué procesar

```bash
.venv\Scripts\python -m mmi.tools.corpus_picker --serve
```

Abre `http://127.0.0.1:8770/`: lista local (`fixtures`, `Pruebas MMI`) + catálogo SharePoint visto. Marca archivos y **Guardar selección** → `out/process-manifest.json`.

## Git

Carpeta local: `C:\Users\User Monitoring\mmi-by-monitoring`.  
En esta máquina no hay `git` en PATH; instalar Git for Windows y luego:

```bash
git init -b main
git add .
git commit -m "Initial commit: MMi by Monitoring scaffold"
```
