# Plan de Implementación — Pipeline de Ingesta y Motor RAG MMI (v3, Qdrant Cloud)

**Documento:** Plan de trabajo por fases — revisión 3 (decisiones cerradas)
**Cambios respecto a v1:** la capa vectorial migra de Supabase/pgvector a **Qdrant Cloud**; embeddings **OpenAI `text-embedding-3-small`**; LLM de generación **OpenAI**; vector disperso **BM25 con fastembed**; OCR **parametrizable con stub** (proveedor pendiente de pruebas).
**Autor:** Manus AI
**Estado:** Aprobado para arranque de Fase 0 (pendiente solo el corpus de arranque)

---

## 1. Visión y principios rectores

El sistema MMI es una **memoria técnica industrial de solo asistencia**: no ejecuta cambios sobre activos, sino que produce *Insights Accionables* que requieren validación humana (protocolo CoVe). Tres principios no negociables gobiernan el diseño:

1. **Trazabilidad absoluta.** Cada fragmento recuperado salta al binario original (`source_file_id`) y registra su método de extracción (`text` u `ocr`).
2. **Integridad histórica.** Prohibido el borrado físico; el versionado lógico (`is_current`, `modified_at`) permite reconstruir el estado del conocimiento en cualquier fecha.
3. **Precisión sobre fluidez.** Ante ausencia o contradicción de evidencia, el sistema rechaza o escala; nunca improvisa.

---

## 2. Decisión de stack: embeddings y base vectorial

### 2.1 Embeddings: recomendación fundamentada

El usuario dispone de API de **Mistral** y de **OpenAI**. La comparativa sobre fuentes públicas arroja el siguiente panorama:

| Criterio | OpenAI `text-embedding-3-small` | OpenAI `text-embedding-3-large` | Mistral `mistral-embed` |
|---|---|---|---|
| Dimensiones | 1536 (truncable Matryoshka) | 3072 (truncable a 256–1536) | 1024 fijas [1] |
| Precio (lista, por 1M tokens) | ~$0.02 [2] | ~$0.13 [2] | ~$0.10 [3] |
| MTEB (inglés, aprox.) | ~62.3 [4] | ~64.6 [4] | ~58.6 [5] |
| Ventana de contexto | 8191 tokens | 8191 tokens | 8192 tokens [6] |
| Truncamiento Matryoshka | Sí | Sí | No |
| Posicionamiento | Mejor valor generalista [2] | Techo de calidad OpenAI | Líder de coste a alto volumen [5] |

**Recomendación: OpenAI `text-embedding-3-small` como modelo principal del MVP**, por cuatro razones:

1. **Valor.** A ~$0.02/1M tokens es 5× más barato que `mistral-embed` (~$0.10/1M) con mejor MTEB (62.3 vs 58.6) [2] [4] [5]. En un corpus industrial con reingestas por versionado, el coste de refresh domina el TCO a partir del año 1 [5].
2. **Multilingüe.** El corpus MMI será mayoritariamente español con documentación OEM en inglés. La familia text-embedding-3 tiene rendimiento multilingüe probado (MIRACL), mientras que la cobertura de Mistral Embed fuera del inglés generalista es más estrecha [5].
3. **Matryoshka.** Permite truncar a 512–1024 dimensiones más adelante si el volumen exige reducir almacenamiento y latencia, sin re-entrenar ni cambiar de proveedor [2].
4. **Dimensión 1536.** Coincide con el DDL del manual (`vector(1536)`), minimizando cambios de diseño.

**Rol de Mistral:** conservar la API como **proveedor de contingencia** y como LLM de generación alternativo si la política de datos exige un proveedor europeo. La abstracción del cliente de embeddings (interfaz `EmbeddingProvider`) permitirá conmutar con un cambio de configuración, asumiendo el coste de re-embedido total del corpus si se migra de proveedor (los vectores no son comparables entre vendors) [5].

> **Nota de diseño:** la elección final debe validarse con el *golden set* de la Fase 6. Si el recall sobre el corpus real cayera más de 2 puntos frente a una alternativa, se reevalúa antes de producción.

### 2.2 Base vectorial: Qdrant

Qdrant aporta tres capacidades que pgvector no resuelve con la misma madurez para este caso:

- **Vectores nombrados (denso + disperso) en un mismo punto.** Permite almacenar el embedding denso (semántico) y un vector disperso (BM25/SPLADE) por chunk, habilitando búsqueda híbrida nativa con fusión (RRF) en una sola llamada [7].
- **Filtrado por payload durante la búsqueda.** `tenant_id`, `is_current`, `criticality_level` y `extraction_method` se filtran en el propio motor vectorial con índices de payload, sin joins ni doble pasada [7].
- **Escala y despliegue.** HNSW configurable, cuantización escalar (4× menos memoria), sharding/replicación y opción on-premise para sectores regulados (minería, energía) [7].

**Consecuencia arquitectónica:** Postgres (Supabase) sigue siendo la **fuente de verdad** para documentos, versionado, activos, chat y RLS; Qdrant almacena **vectores + payload mínimo de filtrado**, referenciando al chunk por UUID. El contenido íntegro del chunk permanece en Postgres para el salto forense y la auditoría.

---

## 3. Arquitectura actualizada

### 3.1 Componentes

| Capa | Componente | Tecnología | Responsabilidad |
|---|---|---|---|
| Ingesta | Orquestador de pipeline | Python 3.11 + asyncio (cola `asyncio.Queue`; worker arq/Dramatiq si se distribuye) | SHA-256, encolado, concurrencia y rate limits |
| Ingesta | Extractores por formato | `openpyxl`/`pandas`, `pdfplumber`/`pypdf`, `python-pptx` | Extracción fiel a la jerarquía del documento |
| Ingesta | OCR bajo demanda | Interfaz `OcrProvider` con stub en MVP; proveedor real (Azure AI Vision / Google Document AI) tras pruebas | Cobertura de escaneados; marca `extraction_method = ocr` |
| Procesamiento | Chunker adaptativo | Reglas por tipo de documento (sección 4 del manual) | Preserva unidades operativas y de seguridad |
| Procesamiento | Embeddings densos | OpenAI `text-embedding-3-small` (1536 dims), lotes con backoff | Vectorización respetando rate limits |
| Procesamiento | Vectores dispersos | BM25 con `fastembed` (sin GPU, MVP simple) | Señal léxica para códigos exactos |
| Datos | Metadatos y verdad | Supabase (Postgres 15+) | Documentos, versionado, activos, chat, RLS |
| Datos | Motor vectorial | **Qdrant Cloud** (cluster gestionado, API key) | Colección con vectores nombrados `dense` + `sparse`, payload filtrable |
| Datos | Binarios | Supabase Storage | Originales vinculados por `source_file_id` |
| Consulta | Motor RAG híbrido | Qdrant `query_points` con fusión denso+disperso + filtro de payload | Recuperación exacta y semántica ponderada por criticidad |
| Consulta | LLM de respuesta | **OpenAI** (misma API que embeddings), salida JSON estructurada, temperatura 0 | Etiqueta de evidencia y citas |
| Operación | Panel CoVe | Next.js + Supabase Auth | Aprobación humana, evidencia y salto al binario |

### 3.2 Modelo de datos

**Postgres (fuente de verdad).** El DDL del manual se mantiene con los cuatro refinamientos ya identificados en v1, más uno nuevo:

- `file_hash` deja de ser `UNIQUE` global; la unicidad es `(tenant_id, file_name, version_number)`.
- `documents.source_file_id` referencia al binario en Storage.
- `document_chunks` conserva el contenido íntegro y `chunk_metadata`, pero **ya no almacena el embedding**: guarda `qdrant_point_id UUID` que referencia al punto en Qdrant.
- RLS explícito en las cinco tablas, verificado con tests de aislamiento.

**Colección Qdrant `mmi_chunks`:**

```python
client.create_collection(
    collection_name="mmi_chunks",
    vectors_config={
        "dense": VectorParams(size=1536, distance=Distance.COSINE),
    },
    sparse_vectors_config={
        "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False)),
    },
    on_disk_payload=True,
)
```

**Payload por punto (mínimo filtrable):**

```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "tenant_id": "uuid",
  "is_current": true,
  "extraction_method": "text",
  "doc_type": "sop",
  "asset_codes": ["COMP-101"],
  "criticality_level": "Crítico Alto",
  "source_file_id": "uuid",
  "page_or_slide": 12
}
```

Índices de payload obligatorios: `tenant_id` (KEYWORD), `is_current` (BOOL), `criticality_level` (KEYWORD), `asset_codes` (KEYWORD), `doc_type` (KEYWORD).

### 3.3 Aislamiento multitenant sin RLS en Qdrant

Qdrant no tiene RLS estilo Postgres; el aislamiento se implementa en dos capas:

1. **Filtro obligatorio en aplicación.** Toda consulta incluye `tenant_id` en el `query_filter` (condición `must`). La capa de acceso a datos es la única vía de consulta y aplica el filtro de forma no omitible.
2. **Verificación.** Tests automatizados cruzando tenants, idénticos en espíritu a los de RLS. Opcionalmente, en Qdrant Cloud puede evaluarse una colección por tenant si el cliente exige aislamiento físico (coste mayor).

La métrica "Error de Aislamiento Tenant = 0%" se mantiene; solo cambia el mecanismo de enforcement.

### 3.4 Flujo de ingesta (actualizado)

1. Recepción → SHA-256 sobre el binario.
2. Hash idéntico y `is_current = true` → **abortar** (sin redundancia de embeddings).
3. Archivo cambiado → versión anterior a `is_current = false` en Postgres **y** actualización del payload en Qdrant (`is_current: false` en los puntos de esa versión); incremento de `version_number`.
4. Extracción por formato; PDF sin capa de texto → OCR automático.
5. Chunking adaptativo por tipo de documento.
6. Embeddings densos (OpenAI) + vector disperso (BM25) en lotes con backoff ante 429.
7. Upsert en Qdrant con payload filtrable; persistencia del chunk en Postgres con `qdrant_point_id`.

### 3.5 Flujo de consulta híbrida

1. Embedding de la consulta (denso) + vector disperso de la consulta.
2. `query_points` con prefetch sobre `dense` y `sparse`, fusión RRF, y `query_filter` con `tenant_id`, `is_current = true` y filtros de activo si aplican.
3. Ponderación por criticidad: boost de resultados con `criticality_level = 'Crítico Alto'` (reordenación en aplicación o fórmula de score).
4. Hidratación: los `chunk_id` recuperados se resuelven contra Postgres para obtener contenido íntegro, metadatos y `source_file_id`.
5. Generación con etiqueta de evidencia y citas; registro en `chat_messages.evidence_links`.

---

## 4. Fases de ejecución (actualizadas)

### Fase 0 — Fundaciones (semana 1)

- Supabase: extensiones, DDL refinado (sin columna `embedding`; con `qdrant_point_id`), RLS verificado con dos tenants.
- Qdrant: colección `mmi_chunks` con vectores nombrados, índices de payload y cliente con `prefer_grpc`.
- Bucket de Storage, esqueleto del pipeline, CI básico.
- **Entregable:** esquema + colección desplegados, aislamiento de tenants verificado en ambos motores.

### Fase 1 — Pipeline de ingesta (semanas 2–3)

- Extractores XLSX (Markdown tabular estricto, `null` preservados, cabeceras repetidas), PDF (página/sección + disparador OCR) y PPTX (slide a slide con speaker notes).
- SHA-256, versionado lógico sincronizado Postgres↔Qdrant, cola asíncrona con rate limiting.
- **Entregable:** ingesta CLI/servicio probada sobre corpus de ejemplo (incluye PDF escaneado y XLSX con celdas vacías).

### Fase 2 — Chunking adaptativo y embeddings (semana 4)

- Reglas del manual (OEM 800–1200/100, SOP 500–800/120, tablas y slides como entidad única).
- Guardas de seguridad: detector de advertencias ("ADVERTENCIA", "PRECAUCIÓN", "LOCKOUT") que prohíbe cortar entre advertencia y paso operativo.
- Cliente de embeddings con abstracción `EmbeddingProvider` (OpenAI por defecto; Mistral conmutable por configuración) y generador de vectores dispersos BM25 con `fastembed` (sin dependencia de GPU).
- **Entregable:** chunker con tests de unidad operativa + indexación dual denso/disperso funcionando.

### Fase 3 — Motor de consulta híbrido (semana 5)

- Consulta Qdrant con prefetch denso + disperso y fusión RRF; filtro obligatorio de tenant y `is_current`.
- Ponderación por `criticality_level` con boost a "Crítico Alto".
- Modo auditoría: consulta sobre versiones históricas (`is_current = false`) a fecha T.
- **Entregable:** endpoint de búsqueda con latencia medida y pruebas de recuperación de códigos exactos.

### Fase 4 — Generación con evidencia y CoVe (semana 6)

- Salida estructurada JSON: `answer`, `evidence_level`, `citations[]` (chunk_id + document_id + página/slide), `confidence_notes`.
- Reglas de rechazo: `not_found` sin evidencia; `conflict` ante contradicción entre documentos vigentes + solicitud automática de revisión técnica.
- Registro en `chat_messages` con `evidence_links`.
- **Entregable:** endpoint de chat que nunca responde sin citas ni etiqueta.

### Fase 5 — Panel operativo (semanas 7–8)

- Auth Supabase con `tenant_id` en JWT.
- Consulta con evidencia expandible y salto al binario; cola de Insights con **Aprobar / Rechazar / Escalar**.
- Vista de auditoría histórica.
- **Entregable:** panel desplegado con flujo CoVe completo.

### Fase 6 — Evaluación y endurecimiento (semana 9)

- Golden set de 50–100 consultas (códigos exactos, diagnósticos semánticos, sin evidencia, documentos en conflicto).
- Comparativa A/B de recall entre `text-embedding-3-small` y `mistral-embed` sobre el corpus real (validación de la recomendación 2.1).
- Carga de ingesta masiva verificando que la latencia de consulta no se degrada.
- **Entregable:** informe de métricas y sistema listo para piloto.

---

## 5. Métricas de éxito y verificación

| Métrica | Objetivo | Método |
|---|---|---|
| Recuperación de términos exactos (códigos) | ≥ 95% | Golden set por código de parte/falla; acierto si el chunk correcto está en top-k (la vía dispersa BM25 es la principal palanca aquí) |
| Trazabilidad de citas | 100% | Toda respuesta `supported`/`partial` incluye `chunk_id` válidos que resuelven al binario |
| Error de aislamiento tenant | 0% | Tests cruzando dos tenants en Postgres (RLS) y en Qdrant (filtro obligatorio) |
| Rechazo correcto ante falta de evidencia | ≥ 90% | Consultas sin soporte; acierto si etiqueta `not_found` |

---

## 6. Riesgos y mitigaciones (actualizados)

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Divergencia Postgres↔Qdrant (chunk en uno y no en otro) | Citas rotas o chunks huérfanos | Escritura en dos fases con reconciliación periódica (job que compara `qdrant_point_id` contra puntos existentes) |
| Aislamiento tenant en Qdrant depende de aplicación | Fuga entre tenants si un filtro se omite | Capa de acceso única con filtro no omitible + tests de aislamiento en CI; colección por tenant si se exige aislamiento físico |
| OCR de baja calidad en planos | Chunks corruptos | Umbral de confianza; cuarentena para revisión |
| Rate limits de embeddings en ingesta masiva | Backlog | Cola con concurrencia limitada, backoff exponencial, priorización de lotes |
| Chunking que rompe unidades de seguridad | Riesgo operativo grave | Guardas en el chunker + test de regresión por SOP |
| Coste de refresh por versionado | Presupuesto | SHA-256 aborta duplicados; solo se reembede lo que cambió [5] |
| Migración futura de proveedor de embeddings | Re-embedido total del corpus | Abstracción `EmbeddingProvider`; decisión validada con golden set antes de producción |

---

## 7. Decisiones cerradas y pendientes

### 7.1 Cerradas

| Decisión | Resolución | Fecha |
|---|---|---|
| Despliegue de Qdrant | **Qdrant Cloud** (cluster gestionado) | Cerrada |
| LLM de generación | **OpenAI** (salida JSON estructurada, temperatura 0) | Cerrada |
| Vector disperso | **BM25 con `fastembed`** (MVP simple, sin GPU) | Cerrada |
| Embeddings | **OpenAI `text-embedding-3-small`** (1536 dims); Mistral como contingencia conmutable | Cerrada |

### 7.2 Pendientes

1. **Proveedor OCR:** pendiente para pruebas. El pipeline se implementa con la interfaz `OcrProvider` y un stub que registra `extraction_method = ocr` sin llamar a ningún API; la elección real (Azure AI Vision / Google Document AI / AWS Textract) se hará con un lote de PDFs escaneados representativos en la Fase 1.

### 7.3 Corpus de arranque: DISPONIBLE

El usuario confirma que dispone de **mucha información real** (manuales OEM, SOP, hojas de cálculo). Esto habilita:

- **Golden set representativo** construido sobre consultas reales del dominio, no sintéticas.
- **A/B de embeddings** (OpenAI vs Mistral) con recall medido sobre el corpus verdadero en la Fase 6.
- **Pruebas de OCR** con PDFs escaneados reales en la Fase 1 para elegir proveedor.

**Mecanismo de entrega:** subir los archivos al chat (formatos XLSX/XLS, PDF, PPTX) o compartir un enlace de descarga. Para el MVP se recomienda un primer lote de **10–20 documentos representativos** que incluya: al menos un PDF escaneado (para calibrar OCR), una hoja de cálculo con celdas vacías (para validar la extracción tabular), un SOP con advertencias de seguridad (para las guardas del chunker) y un manual OEM extenso (para el chunking de 800–1200 tokens). El resto del corpus se ingesta en la fase de carga masiva una vez validado el pipeline.

---

## 8. Siguiente paso

Con todas las decisiones cerradas y el corpus real disponible, la **Fase 0 arranca de inmediato**: esquema Postgres con RLS, colección `mmi_chunks` en Qdrant Cloud con vectores nombrados e índices de payload, y esqueleto del pipeline con `EmbeddingProvider` y `OcrProvider` parametrizables. El primer lote de 10–20 documentos representativos se usa ya en la Fase 1 para calibrar extractores y OCR; el golden set de la Fase 6 se construye sobre consultas reales del dominio. Cada fase produce un entregable verificable de forma independiente, de modo que el piloto pueda acotarse (ingesta + consulta sin panel) si el calendario lo exige.

---

## Referencias

1. [Mistral Embeddings API — Mistral AI Cookbook](https://docs.mistral.ai/resources/cookbooks/mistral-embeddings-embeddings) — `mistral-embed` genera vectores de dimensión 1024.
2. [New embedding models and API updates — OpenAI](https://openai.com/index/new-embedding-models-and-api-updates/) — precio de `text-embedding-3-small` reducido 5× respecto a ada-002 (~$0.02/1M tokens).
3. [Mistral API Pricing](https://mistral.ai/pricing/api/) — `mistral-embed` a $0.10 por millón de tokens.
4. [OpenAI Community — Embeddings performance small vs large](https://community.openai.com/t/embeddings-performance-difference-between-small-vs-large-at-1536-dimensions/618069) — MTEB 62.3% (small) vs 64.6% (large).
5. [Embedding Model Cost Calculator: Vendor Comparison 2026 — Digital Applied](https://www.digitalapplied.com/blog/embedding-model-cost-calculator-vendor-comparison-2026) — Mistral como líder de coste a alto volumen (~58.6 MTEB), matemática de refresh y TCO.
6. [Mistral Embed 2312 — OpenRouter](https://openrouter.ai/mistralai/mistral-embed-2312) — 1024 dimensiones, hasta 8192 tokens por entrada.
7. [Qdrant Documentation](https://qdrant.tech/documentation/) — vectores nombrados, vectores dispersos, filtrado por payload, HNSW y cuantización.
