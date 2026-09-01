# Mapa de Conocimiento MMI — Plan de integración

**Fecha:** 2026-09-01  
**Estado:** ⏳ planificado (post Fase D)  
**Rama sugerida:** `mapa-conocimiento` (después de `analisis-datos`)  
**Objetivo:** exploración visual del corpus — grafo estilo Obsidian con búsqueda semántica, filtros industriales y asistente contextual sobre nodos seleccionados.

**Relacionado:** [`plan.md`](plan.md) · [`plan-analisis-datos.md`](plan-analisis-datos.md) · [`plan-mmi-motor.md`](plan-mmi-motor.md) · [`plan-fase-c.md`](plan-fase-c.md)

---

## 1. Posición en el producto

El Mapa de Conocimiento **no reemplaza** las pantallas actuales; las complementa:

| Pantalla | Modo de uso | Usuario |
|----------|-------------|---------|
| `search.html` | Lista de fragmentos | “¿Dónde dice X?” |
| `rag.html` | Respuesta redactada + citas | “Explícame X” |
| `motor.html` | Activo + síntoma | “¿Qué pasa con STG-01?” |
| **`mapa.html`** | **Exploración relacional** | “¿Qué está conectado con X?” |

```
                    ┌─────────────────┐
  consulta texto ──►│ Buscador        │──► semilla de nodos
                    │ semántico       │
                    └────────┬────────┘
                             ▼
┌──────────┐    ┌────────────────────────┐    ┌──────────────────┐
│ Filtros  │───►│ Grafo central        │◄──►│ Panel derecho    │
│ activo   │    │ (Obsidian / force)   │    │ contenido + meta │
│ área     │    │ nodos + aristas      │    │ chunk / doc      │
│ falla    │    └──────────┬───────────┘    └────────┬─────────┘
│ fecha    │               │                         │
│ documento│               │ Expandir relaciones     │
└──────────┘               ▼                         ▼
                    similitud ≥ umbral          Asistente contextual
                    (vectores + tags)           (/api/ask · nodos)
```

---

## 2. Especificación UI (`mapa.html`)

### Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [🔍 Buscador semántico superior — query + Enter]     similitud ≥ [0.72 ▼] │
├────────────┬─────────────────────────────────────────────┬─────────────────┤
│ Filtros    │                                             │ Panel derecho   │
│            │         GRAFO CENTRAL                       │                 │
│ Activo     │    ○ doc ──○ chunk ──○ concepto            │ Título / tipo   │
│ [STG-01 ▼] │         \    |    /                        │ Página · rev    │
│ Área       │          ○──○──○                           │ Activo · dominio│
│ [ENFR ▼]   │                                             │ ─────────────── │
│ Falla      │   [Global] [Documentos] [Conceptos]        │ extracto…       │
│ [vibración]│                                             │ [Ver fuente]    │
│ Fecha      │   [ Expandir relaciones ]  selección: 3     │ [Preguntar ▶]   │
│ [2024-25]  │                                             │                 │
│ Documento  │                                             │                 │
│ [FMECA ▼]  │                                             │                 │
└────────────┴─────────────────────────────────────────────┴─────────────────┘
```

### Controles

| Control | Comportamiento |
|---------|----------------|
| **Buscador superior** | `HybridSearchEngine` + reranker; top-k chunks como nodos semilla |
| **Grafo central** | Force-directed (p. ej. `d3-force` o `vis-network`); zoom, pan, multiselección |
| **Filtros** | Recortan nodos/aristas visibles; reutilizan metadatos ya indexados |
| **Panel derecho** | Chunk o documento seleccionado: cita, `document_key`, `asset_codes`, confianza OCR |
| **Similitud mínima** | Umbral aristas por coseno vectorial (default 0.72, ajustable) |
| **Expandir relaciones** | 1-hop desde selección: vecinos por similitud, mismo `document_key`, tags EAM compartidos |
| **Vistas** | **Global** (mixto) · **Documentos** (nodos doc + chunks) · **Conceptos** (tags, modos falla, activos) |
| **Asistente** | Envía nodos seleccionados como contexto a `/api/ask` o panel lateral RAG |

---

## 3. Modelo de grafo

### Tipos de nodo

| Tipo | Origen | ID ejemplo |
|------|--------|------------|
| `document` | Supabase `documents` | `doc:{uuid}` |
| `chunk` | Supabase `chunks` + Qdrant | `chunk:{uuid}` |
| `asset` | `asset_codes` / catálogo EAM B4 | `asset:STG-01-X` |
| `concept` | Extracción: modo falla, RPN, sección | `concept:fmeca:desalineamiento` |

### Tipos de arista

| Relación | Peso | Fuente |
|----------|------|--------|
| `similar_to` | score coseno | Qdrant nearest neighbors |
| `part_of` | 1.0 | chunk → document |
| `mentions_asset` | 0.9 | chunk `asset_codes` |
| `same_document_key` | 0.85 | versiones / anexos mismo `document_key` |
| `co_occurs` | freq | Fase D — co-ocurrencia en análisis de datos |
| `conflicts_with` | alerta | C2 `search/conflicts.py` |

---

## 4. APIs nuevas

| Método | Ruta | Uso |
|--------|------|-----|
| POST | `/api/graph/search` | Semilla: query → nodos + aristas iniciales |
| POST | `/api/graph/expand` | `node_ids[]`, `min_similarity`, `depth=1` |
| GET | `/api/graph/node/{id}` | Metadatos + contenido para panel derecho |
| POST | `/api/graph/ask` | Pregunta + `node_ids[]` → RAG acotado al subgrafo |
| GET | `/api/graph/filters` | Opciones activo, área, tipo, rango fechas |

**Reutiliza:** `HybridSearchEngine`, `search/rerank.py`, `search/answer.py`, `catalog/assets.py`, `search/conflicts.py`.

---

## 5. Fases de implementación

### E1 — Grafo mínimo viable (2 semanas)

| # | Tarea | Archivos |
|---|-------|----------|
| E1.1 | Modelo `GraphNode`, `GraphEdge`, builder desde search hits | `src/mmi/graph/models.py` | ✅ |
| E1.2 | API `search` + `expand` (similitud Qdrant) | `src/mmi/graph/builder.py`, `api_routes.py` | ✅ |
| E1.3 | UI `mapa.html` — grafo + panel derecho | `src/mmi/graph/page.py` | ✅ |
| E1.4 | Slider similitud mínima + botón expandir | JS en `page.py` | ✅ |
| E1.5 | Registro en `serve_local` + nav | `serve_local.py`, `review_shell.py` | ✅ |

**DoD E1:** buscar “FMECA enfriamiento” → grafo con ≥5 nodos; clic → panel con cita; expandir 1-hop.

### E2 — Filtros y vistas (1 semana)

| # | Tarea |
|---|-------|
| E2.1 | Filtros activo, área (`dominio`), documento (`tipo`, `document_key`) |
| E2.2 | Filtro fecha (`version_label`, `indexed_at`) |
| E2.3 | Filtro falla / síntoma (texto en chunk + conceptos FMECA) |
| E2.4 | Toggle Global / Documentos / Conceptos |

### E3 — Asistente contextual (1 semana)

| # | Tarea |
|---|-------|
| E3.1 | Selección múltiple de nodos |
| E3.2 | `/api/graph/ask` — contexto = chunks de nodos seleccionados |
| E3.3 | Panel “Preguntar sobre selección” (reusa prompt RAG + conflictos C2) |
| E3.4 | Enlace “Abrir en Motor MMI” si hay activo en selección |

### E4 — Conceptos y enriquecimiento (opcional)

| # | Tarea |
|---|-------|
| E4.1 | Nodos `concept` desde FMECA/RCM (modo falla, RPN) |
| E4.2 | Aristas `co_occurs` desde Fase D |
| E4.3 | Destacar conflictos multi-versión en grafo (borde rojo C2) |
| E4.4 | Persistencia subgrafo favorito (localStorage → Supabase) |

---

## 6. Dependencias y prerequisitos

| Prerequisito | Estado | Uso en mapa |
|--------------|--------|-------------|
| Indexación ODS1 | ✅ ~1274 docs | Nodos chunk/document |
| Búsqueda híbrida + reranker | ✅ C1 | Semilla semántica |
| Catálogo EAM B4 | ✅ | Nodos/filtro activo |
| Conflictos C2 | ✅ | Aristas alerta |
| Golden set C3 | ✅ | Validar calidad expansión |
| **Fase D análisis datos** | 🔄 rama actual | Pesos `co_occurs`, gaps cobertura |
| Filtros UI búsqueda | ⏳ pendiente Fase 2 | Reutilizar misma capa de filtros |

**Orden recomendado:**

```
Fase D (analisis-datos)  →  métricas y co-ocurrencia
        ↓
Fase E1 (grafo MVP)      →  mapa.html básico
        ↓
Fase E2–E3 (filtros + asistente)
        ↓
Fase 3 producto (auth, cloud)
```

---

## 7. Stack técnico sugerido

| Capa | Opción | Notas |
|------|--------|-------|
| Grafo UI | `vis-network` o `cytoscape.js` | Obsidian-like; evitar dependencia pesada al inicio |
| Layout | force-directed | Agrupa por similitud y `document_key` |
| Backend | Python existente | Sin nuevo servicio; extiende `serve_local` |
| Vectores | Qdrant `search` + `recommend` | Vecinos para aristas `similar_to` |
| Estado UI | URL hash + `sessionStorage` | `?q=...&sim=0.72&view=documents` |

---

## 8. Métricas de éxito

- Tiempo hasta primer grafo útil &lt; 3 s (semilla 10 nodos)
- Expansión 1-hop &lt; 2 s
- Usuario encuentra documento relacionado no visto en top-5 búsqueda lineal (eval manual 10 casos)
- `/api/graph/ask` cita solo nodos del subgrafo seleccionado

---

## 9. Referencias código existente

| Módulo | Reuso |
|--------|-------|
| `search/engine.py` | Semilla semántica, metadatos chunk |
| `search/rerank.py` | Orden post-recuperación |
| `search/answer.py` | Asistente contextual |
| `search/conflicts.py` | Aristas conflicto |
| `catalog/assets.py` | Nodos activo |
| `motor/analyze.py` | Puente activo+síntoma desde selección |
| `tools/search_cli.py` | Patrón HTML estático + API |

---

## 10. Checklist integración al plan

- [ ] Rama `mapa-conocimiento` desde `main` (post merge `analisis-datos`)
- [ ] E1.1–E1.5 grafo MVP
- [ ] Entrada en nav: Búsqueda · RAG · **Mapa** · Motor · Revisión
- [ ] Golden set ampliado con 5 casos “exploración relacional”
- [ ] Documentar en `plan.md` § Fase E
