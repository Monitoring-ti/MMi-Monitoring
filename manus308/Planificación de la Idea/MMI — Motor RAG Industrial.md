# MMI — Motor RAG Industrial

Motor RAG industrial: **Postgres (Supabase)** como fuente de verdad y **Qdrant Cloud** como motor vectorial híbrido (dense + sparse con RRF).

## Estado

| Fase | Estado | Detalle |
|---|---|---|
| **Fase 0 — Fundaciones** | ✅ Completa | Colección Qdrant + DDL Postgres con RLS verificado |
| **Fase 1 — Pipeline de ingesta** | ✅ Completa | Extractores + chunking + versionado + lote 1 indexado |
| **Fase 2 — Chunking por dominio** | ✅ Completa | Secciones, cortes semánticos, guardas refinadas, lote reindexado |
| **Carga masiva** | ✅ Completa | Corpus completo indexado (48 documentos, 1517 chunks) |

## Carga masiva — Corpus completo

**48 documentos indexados, 1 517 chunks, ~550 000 tokens** (Postgres y Qdrant consistentes).

| Métrica | Valor |
|---|---|
| Archivos procesables | 60 (5 imágenes omitidas) |
| Documentos indexados | 48 (40 nuevos + 8 ya existentes) |
| Chunks totales | 1 517 |
| Tokens totales | ~550 000 |
| Formatos | PDF 16, DOCX 20, XLSX 19, PPTX 9 |
| Tiempo de ingesta | ~400 s (60 archivos) |

**Optimizaciones aplicadas:** lote Postgres de 500 filas, upsert Qdrant con `upload_points` (batch 128, 2 hilos).

**Versionado:** 8 documentos ya existentes se detectaron como duplicados por SHA-256 y no se reindexaron. El par Rev 4/5/6 de la guía y el procedimiento BCK coexisten como versiones.

**Notas:**
- `LIBRO SOMA DIGITAL FINAL.pdf` (18,7 MB) se redescargó completo tras detectarse truncado y se indexó (286 chunks).
- 11 plantillas XLSX vacías (solo cabecera) no generan chunks — comportamiento correcto.
- 5 imágenes (jpg/png) se omiten de la ingesta RAG (no son documentos de texto).

## Fase 2 — Chunking refinado

**7 documentos reindexados, 556 chunks, ~247 500 tokens** (Postgres y Qdrant consistentes).

Mejoras aplicadas sobre el chunker de la Fase 1:

| Mejora | Antes | Después |
|---|---|---|
| `section_path` en PDF | ausente | 105/106 chunks del SOP con sección (p.ej. `8.12.1.3 ASPECTOS FISIOLÓGICOS`) |
| Cortes | por tokens, a media frase | en límite de sección/párrafo |
| Chunks cortos PPTX | 10 <80 tok | 1 <40 tok (fusión de slides) |
| Guardas de seguridad | advertencia aislada | advertencia + paso juntos, etiqueta `seguridad` |

El reindexado borra y recrea cada documento en Postgres y Qdrant de forma consistente (función `reingest`).

## Fase 1 — Resultados del lote 1

**7 documentos indexados, 482 chunks, ~242 000 tokens.**

| Archivo | Tipo | Chunks | Versión |
|---|---|---|---|
| NCC-030_REV02.pdf | norma | 37 | REV02 |
| SGP-07MYC-GUIGS-00001 … Rev 6.pdf | guia | 66 | Rev 6 |
| SGP-07MYC-GUIGS-00001 Rev 5.pdf | guia | 62 | Rev 5 |
| SGPD-07MYC-PROGS-0001 Procedimiento….pdf | sop | 89 | — |
| Anexo C Check List ….xlsx | tabla | 115 | — |
| FMECA MONITORING 092021 rev 1.pptx | presentacion | 51 | rev 1 |
| RCM MONITORING 072021 rev 4….pptx | presentacion | 62 | rev 4 |

**Validado:**
- **Versionado SHA-256**: Rev 5 y Rev 6 de la guía coexisten con hashes distintos; el RCM re-ingresado se detectó como duplicado.
- **Búsqueda híbrida RRF** sobre datos reales con filtro de tenant + `is_current`.
- **Guardas de seguridad**: 6 chunks del SOP marcados `criticality_level=seguridad`.
- **Detección de activos**: códigos tipo `IFC-78` extraídos a `asset_codes`.

> Nota: `SGPD-07MYC-FRMGS-0035 FMECA.xlsx` es una **plantilla vacía** (solo cabecera, sin filas de datos), por lo que no genera chunks. Es el comportamiento correcto.

## Estructura

```
mmi/
├── .env                      # Credenciales (NO versionar; chmod 600)
├── .gitignore
├── db/
│   └── 001_schema.sql        # DDL Postgres: 7 tablas + RLS + índices
├── qdrant/
│   └── create_collection.py  # Crea/verifica la colección mmi_chunks
├── pipeline/
│   └── providers.py          # EmbeddingProvider, SparseEncoder, OcrProvider, IngestPipeline
└── scripts/
    └── smoke_qdrant.py       # Smoke test end-to-end (embed + upsert + búsqueda RRF)
```

## Configuración

Las credenciales viven en `.env` (cargar con `set -a && . ./.env && set +a`):

| Variable | Servicio | Uso |
|---|---|---|
| `QDRANT_URL` | Qdrant Cloud | URL del cluster |
| `QDRANT_API_KEY` | Qdrant Cloud | Autenticación (JWT) |
| `OPENAI_API_KEY` | OpenAI | Embeddings + generación |

> **Nota:** la key de OpenAI es de la API real (`api.openai.com`), no del proxy del sandbox. El provider fuerza `base_url="https://api.openai.com/v1"`.

## Colección Qdrant `mmi_chunks`

- **Vector denso `dense`**: 1536 dims, distancia COSINE (OpenAI `text-embedding-3-small`).
- **Vector disperso `sparse`**: BM25 vía fastembed (`Qdrant/bm25`), índice en disco.
- **Payload indexado**: `tenant_id`, `document_id`, `tipo`, `dominio`, `criticality_level`, `extraction_method`, `section_path`, `asset_codes` (KEYWORD), `is_current` (BOOL), `chunk_index` (INTEGER).

### Recrear la colección (destructivo)

```bash
set -a && . ./.env && set +a
python3 qdrant/create_collection.py --recreate
```

## Aplicar el DDL en Supabase

El DDL está listo pero **pendiente de aplicar** porque aún no tengo la connection string de Supabase. Dos opciones:

1. **Tú lo ejecutas**: abre el SQL Editor de Supabase y pega el contenido de `db/001_schema.sql`.
2. **Yo lo ejecuto**: pásame la connection string (`postgresql://postgres:[pass]@db.xxxx.supabase.co:5432/postgres`).

El DDL crea las 7 tablas (`tenants`, `app_users`, `assets`, `documents`, `chunks`, `chat_sessions`, `chat_messages`), activa RLS en todas, y siembra el tenant `monitoring`.

## Smoke test

Valida embed denso (OpenAI) + disperso (BM25) + upsert + búsqueda híbrida RRF con filtro de tenant:

```bash
set -a && . ./.env && set +a
python3 scripts/smoke_qdrant.py
```

Resultado verificado: la búsqueda "precauciones de seguridad para operar bomba" rankea primero el chunk de `criticality_level=seguridad` (BOM-210) sobre el chunk normal. Los puntos de prueba se eliminan al final.

## Siguiente fase

**Fase 1 — Pipeline de ingesta**: extractores XLSX/PDF/PPTX sobre el lote 1 (`/home/ubuntu/mmi_corpus/lote1/`), versionado SHA-256 y registro en Postgres. Requiere el DDL aplicado en Supabase.
