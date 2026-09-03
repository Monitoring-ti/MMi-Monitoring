# Plan — Vitrina de ingesta MMI (`mmi.monitoring.lat`)

**Fecha:** 2026-09-03 (actualizado)  
**Rama:** `feature/mmi-operational-web`  
**Dominio:** `https://mmi.monitoring.lat`  
**Relacionado:** [`plan.md`](plan.md) · [`plan-integracion-ui.md`](plan-integracion-ui.md) · [`deploy/RAILWAY.md`](../deploy/RAILWAY.md)

> **Nombre:** *vitrina de ingesta* = escaparate público del **resultado** de la ingesta  
> (corpus indexado + pruebas + ejemplos). **No** es el panel de administrar/cargar documentos.

---

## 0. Tres bloques separados (no mezclar)

```
┌─────────────────────────────────────────────────────────────────┐
│  A · INGESTA (local Monitoring — CERRADA)                       │
│  Manifest · Fase 0 · OCR · indexación · review                  │
│  ✅ Hecha. No se expone en la web. Propiedad del equipo dev.    │
└───────────────────────────────┬─────────────────────────────────┘
                                │ publica solo artefactos de salida
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  B · RESULTADOS DE PRUEBAS (web — solo lectura)                 │
│  Smoke · golden set · validación RAG · carga (resumen)          │
│  HTML/JSON congelados tras cada corrida local                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │ demuestra que el índice responde
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  C · EJEMPLOS SIMPLES (web — consulta guiada)                   │
│  Consultas predefinidas del corpus · búsqueda / RAG             │
│  Sin motor complejo ni tablas de 1500 documentos                │
└─────────────────────────────────────────────────────────────────┘
```

| Bloque | Dónde | Qué ve el visitante |
|--------|-------|---------------------|
| **A Ingesta** | PC dev / CI local | Nada (fuera de la web) |
| **B Pruebas** | `mmi.monitoring.lat` | “Estas pruebas pasaron” + métricas |
| **C Ejemplos** | `mmi.monitoring.lat` | Botones con consultas ejemplo → search/rag |

**La web no administra corpus.** Solo muestra evidencia de que la ingesta y las pruebas corrieron bien, y permite probar consultas acotadas.

---

## 1. Idea central (alcance v1)

La ingesta **ya está OK** y permanece en local.  
`mmi.monitoring.lat` es la **vitrina de ingesta**:

1. Explicar qué quedó indexado (corpus del proyecto en Qdrant/Supabase).
2. Mostrar **resultados de pruebas** (informes estáticos).
3. Ofrecer **ejemplos simples** de consulta (no un panel de ingesta ni revisión de manifest).

Sin perfiles en v1 · sin indexar en Google · demo abierta (`MMI_VITRINA_OPEN=1`); Basic Auth opcional si se cierra.

---

## 2. Objetivos de la web (solo B + C)

| # | Objetivo |
|---|----------|
| 1 | Landing clara: vitrina de ingesta, qué está operativo, cómo usar un ejemplo |
| 2 | Página **Pruebas** con resumen smoke + golden + validación RAG |
| 3 | Página **Ejemplos** con consultas del corpus del proyecto |
| 4 | Consulta en vivo (ejemplos + caja libre) en search/rag |
| 5 | Nota visible: **la ingesta se gestiona internamente** por Monitoring |

**Fuera de alcance v1:** tabla completa de docs, review hub, corpus picker, motor diagnóstico completo, mapa, portal dev, formularios de carga.

---

## 3. Alcance funcional

### 3.1 En la web (`mmi.monitoring.lat`)

| Módulo | Ruta | Fuente de datos | Qué muestra |
|--------|------|-----------------|-------------|
| **Inicio** | `/` | generado | Hero + 2 tarjetas (Pruebas · Ejemplos) + guía de uso |
| **Pruebas** | `/pruebas.html` | JSON sync local | Smoke, golden MRR/recall, validación RAG, fecha de corrida |
| **Ejemplos** | `/ejemplos.html` | `search/examples.py` | Tarjetas NCC, FMECA, matrices… → enlace a search/rag |
| **Búsqueda** | `/search.html` | API en vivo | Fragmentos; panel de ejemplos embebido (ya existe) |
| **Consulta RAG** | `/rag.html` | API en vivo | Pregunta + citas; ejemplos embebidos (ya existe) |

APIs necesarias en producción: `POST /api/search`, `POST /api/ask`, `GET /api/motor/health` (healthcheck).

### 3.2 Fuera de la web (local dev / ingesta cerrada)

| Qué | Por qué |
|-----|---------|
| Todo el pipeline de ingesta | Bloque A — ya OK, no se publica |
| `ingestion-results.html` (tabla completa) | Es stats de ingesta, no vitrina de pruebas |
| `review.html`, `corpus-picker`, `source-review` | Herramientas internas |
| `motor.html`, `mapa.html` | Fuera de “ejemplos simples” v1 |
| `POST /api/ingestion-action` | Bloqueado en producción |
| Portal dev (`landing-catalog` completo) | Solo local |

### 3.3 Artefactos a sincronizar local → VPS

Solo los de **pruebas**, no el manifest completo:

| Archivo | Uso en web |
|---------|------------|
| `query-smoke.json` | Tarjeta smoke 3/3 |
| `golden-set-eval.json` | MRR, recall@5, por categoría |
| `rag-validation.json` | Batería 10 consultas |
| `load-test-report.json` | Latencia p95 (opcional, resumen) |
| `ingestion-results.json` | **Solo** KPIs de cabecera (docs indexados, fecha) — no tabla de docs |

**No sync:** `analysis-status.json` completo, `ingestion-registry.json`, `ocr-staging/`, `review.html`.

---

## 4. Arquitectura de despliegue

```
monitoring.lat (Hostinger)
    └── enlace / redirect ──►  mmi.monitoring.lat

mmi.monitoring.lat (DNS A → VPS 2.25.197.231)
    │
    ▼
nginx :443  (TLS + Basic Auth + noindex headers)
    │
    ├── /              landing operativa (generada)
    ├── /stats.html    estadísticas (solo lectura)
    ├── /search.html   búsqueda
    ├── /rag.html      consulta RAG
    ├── /motor.html    motor diagnóstico
    ├── /mapa.html     mapa (opcional)
    │
    └── /api/*  ──►  mmi-api :8773 (127.0.0.1, no expuesto)
                        │
                        ├── Qdrant Cloud (vectores)
                        ├── Supabase (metadatos PG)
                        └── OpenRouter (generación RAG/motor)

Pipeline local (Monitoring dev)
    ├── ingesta + indexación
    ├── genera out/analysis-status.json, ingestion-results.json, etc.
    └── sync periódico de JSON stats → VPS (/opt/mmi/out/)
```

**VPS KVM 4 (16 GB RAM):** suficiente para nginx + API Python + n8n coexistiendo.  
La ingesta **no corre en el VPS**; solo la API de lectura y archivos JSON de estadísticas.

---

## 4.1 Alternativa — despliegue **sin VPS**

Si no quieren administrar el servidor (`ssh`, nginx, certbot, Docker), la misma web operativa puede desplegarse con **servicios gestionados**. Hostinger sigue siendo solo **DNS**; el VPS (y n8n) queda aparte o apagado para MMI.

### Arquitectura recomendada (sin VPS)

```
monitoring.lat (Hostinger)
    └── redirect / enlace ──►  mmi.monitoring.lat

mmi.monitoring.lat (DNS CNAME → Vercel)
    │
    ▼
Vercel — frontend estático / Next.js
    │  proxy /api/*  (rewrites)
    ▼
Railway o Render — API Python MMI (contenedor gestionado)
    │
    ├── Qdrant Cloud
    ├── Supabase
    └── OpenRouter

Local (Monitoring dev)
    └── ingesta + sync JSON stats → repo o Storage → redeploy Vercel
```

| Pieza | Servicio | Rol |
|-------|----------|-----|
| **Web** (landing, stats HTML, search/rag/motor) | **Vercel** | CDN, HTTPS, `noindex`, Password Protection |
| **API** (`serve_local` / Docker) | **Railway** o **Render** | Python 24/7 sin administrar OS |
| **DNS** | **Hostinger** | `CNAME mmi` → `cname.vercel-dns.com` |
| **Índice** | Qdrant + Supabase | Ya en nube (sin cambio) |
| **Stats JSON** | Git / Supabase Storage / Vercel Blob | Actualización tras cada lote local |

### Por qué no basta solo Vercel

Vercel **no ejecuta** el backend Python completo (Qdrant híbrido, Motor, RAG). Opciones:

| Enfoque | Consultas en vivo | Complejidad |
|---------|-------------------|-------------|
| **Vercel + Railway/Render** (recomendado) | ✅ Sí | Media — un `Dockerfile` + env vars |
| **Solo Vercel (estático)** | ❌ No (solo stats congeladas) | Baja — útil como preview |
| **Reescribir API en Node serverless** | ✅ Sí | Alta — no recomendado ahora |

### Configuración mínima

**Vercel** (proyecto Next.js o carpeta `out/` estática):

```env
MMI_API_URL=https://mmi-api-production.up.railway.app
MMI_DEPLOY_MODE=operational
```

**Railway / Render** (mismo `.env` que local, sin commitear):

```env
MMI_DEPLOY_MODE=operational
QDRANT_URL=...
SUPABASE_URL=...
OPENROUTER_API_KEY=...
OPENAI_API_KEY=...
```

**Hostinger DNS:**

| Tipo | Nombre | Valor |
|------|--------|-------|
| CNAME | `mmi` | `cname.vercel-dns.com` |

### Sync de estadísticas sin VPS

Tras cada lote en local:

1. Generar JSON: `python -m mmi.tools.ingestion_results`
2. **Opción A — Git:** commit `out/ingestion-results.json` + `analysis-status.json` en rama `stats/ods1` → Vercel redeploy automático.
3. **Opción B — Storage:** subir JSON a Supabase Storage; la landing lee `GET` público (solo stats, sin secretos).
4. **Opción C — API:** Railway expone `GET /api/ingestion-results` leyendo archivos montados en volumen (sync vía `scp` o Action).

Las **consultas RAG** no dependen de esos JSON; usan Qdrant/Supabase en tiempo real vía Railway.

### Seguridad sin VPS

| Medida | Dónde |
|--------|-------|
| `noindex` + `robots.txt` | Vercel headers / `vercel.json` |
| Acceso sin perfiles | **Vercel Deployment Protection** (password) o Basic Auth en Railway |
| Secretos | Vercel + Railway dashboards |
| CORS API | Solo `https://mmi.monitoring.lat` |

### Comparativa rápida

| | VPS Hostinger | Sin VPS (Vercel + Railway) |
|--|---------------|----------------------------|
| Administración | SSH, nginx, updates | Casi cero |
| Coste extra | Ya pagado | Vercel free/pro + Railway ~$5–20/mes |
| n8n en mismo server | ✅ | n8n sigue en VPS aparte |
| Consultas + stats | ✅ | ✅ |
| Adecuado si… | Quieren control total | Quieren menos ops |

### Fase de despliegue sin VPS (O4-alt)

1. `Dockerfile` para `mmi.tools.serve_local` (o gunicorn wrapper).
2. Deploy en Railway con env de producción.
3. Proyecto Vercel con proxy `/api/*` → URL Railway.
4. DNS `mmi.monitoring.lat` → Vercel.
5. Password Protection en Vercel.
6. CI local o GitHub Action para publicar stats JSON.

---

### 5.1 Landing (`/`) — vitrina de ingesta (no panel de carga)

```
┌─────────────────────────────────────────────────────────────┐
│  MMI · Vitrina de ingesta · Monitoring                      │
├─────────────────────────────────────────────────────────────┤
│  Corpus indexado en nube · pruebas del lote                 │
│  La ingesta es interna Monitoring — aquí solo resultados.   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │  Resultados pruebas │  │  Ejemplos consulta  │          │
│  │  Smoke · MRR · RAG  │  │  NCC · FMECA · GUIGS│          │
│  │  Ver informe →      │  │  Probar ejemplo →   │          │
│  └─────────────────────┘  └─────────────────────┘          │
├─────────────────────────────────────────────────────────────┤
│  Cómo consultar (3 pasos)                                   │
│  1. Mirá las pruebas — confirma que el índice responde      │
│  2. Elegí un ejemplo — o escribí en Búsqueda / RAG          │
│  3. Revisá la cita — documento y fragmento son la evidencia │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Página Pruebas (`/pruebas.html`)

| Sección | Datos | Presentación |
|---------|-------|--------------|
| Smoke | `query-smoke.json` | 3 casos (NCC, FMECA, GUIGS) + pass/fail |
| Golden set | `golden-set-eval.json` | MRR 0,91 · recall@5 100% · 35 casos |
| Validación RAG | `rag-validation.json` | 10/10 búsqueda OK |
| Resumen corpus | cabecera `ingestion-results.json` | “1274 indexados” sin tabla de docs |
| Carga *(opcional)* | `load-test-report.json` | p50/p95 latencia |

Todo **estático** — no live bar de ingesta.

### 5.3 Página Ejemplos (`/ejemplos.html`)

Reutiliza categorías de `src/mmi/search/examples.py`:

| Categoría | Ejemplo |
|-----------|---------|
| NCC-030 | criticidad mantenibilidad |
| GUIGS | alcance proyectos |
| FMECA | modos falla enfriamiento |
| Matrices | MRI / MSO / SPCI |

Cada tarjeta → `search.html?q=…` o `rag.html?q=…`.

### 5.4 Nav vitrina (mínima)

| Enlace | Etiqueta |
|--------|----------|
| `/` | Inicio |
| `/pruebas.html` | Pruebas |
| `/ejemplos.html` | Ejemplos |
| `/search.html` | Búsqueda |
| `/rag.html` | Consulta |

Sin Ingesta · Revisión · Motor · Mapa en nav pública.

---

## 6. Diseño de consultas

### 6.1 Tres modos de consulta

```
                    ┌─────────────────┐
                    │  Usuario        │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   ┌───────────┐      ┌───────────┐      ┌───────────┐
   │ BÚSQUEDA  │      │ RAG ASK   │      │ MOTOR     │
   │ híbrida   │      │ pregunta  │      │ activo +  │
   │           │      │ + citas   │      │ síntoma   │
   └─────┬─────┘      └─────┬─────┘      └─────┬─────┘
         │                  │                  │
         ▼                  ▼                  ▼
   POST /api/search   POST /api/ask     POST /api/motor/analyze
         │                  │                  │
         └──────────────────┼──────────────────┘
                            ▼
                   HybridSearchEngine
                   (Qdrant + BM25 + Supabase)
                            │
                            ▼
                   OpenRouter (solo ask/motor)
```

| Modo | Cuándo usarlo | Entrada | Salida |
|------|---------------|---------|--------|
| **Búsqueda** | Sabe qué buscar (tag, texto, norma) | `query`, `limit` | Lista de chunks con score, doc, página |
| **RAG** | Pregunta abierta ("¿cuál es el límite de vibración…?") | `query`, `limit` | Respuesta + referencias `[n]` + conflictos |
| **Motor** | Falla en equipo concreto | `asset_id`, `symptom`, `window` | Hipótesis, hechos verificados, checks físicos |

### 6.2 Flujo UX — Consulta RAG (`/rag.html`)

1. Usuario escribe pregunta en textarea.
2. `POST /api/ask` → loading con tiempo transcurrido.
3. Panel respuesta: texto con citas inline.
4. Panel referencias: documento, chunk, score, enlace a fragmento si existe.
5. Banner amarillo si `conflicts` detecta versiones contradictorias.
6. Botón "Ver evidencia" → `POST /api/ask-details` sección `sources`.

**Copy de ayuda en pantalla:**

- Use nombres de activo (`CTS-DCH-ENF`), tags (`TE-401A`) o tipo de documento.
- Si no hay resultados, pruebe búsqueda directa con términos más cortos.
- Las citas son la fuente de verdad; la respuesta LLM no sustituye el documento.

### 6.3 Flujo UX — Motor MMI (`/motor.html`)

1. Selector de activo (lista desde índice / fixture operativo).
2. Campo síntoma (texto libre).
3. Ventana temporal (`24h`, `7d`, …).
4. `POST /api/motor/analyze` → workspace diagnóstico.
5. Panel derecho: fuentes vía `motor/details`.
6. Sin validación humana en v1 operativa (opcional fase 2).

### 6.4 Flujo UX — Estadísticas (`/stats.html`)

Basado en `ingestion-results.html` **filtrado**:

| Sección | Mostrar | Ocultar |
|---------|---------|---------|
| KPIs globales | ✅ | — |
| Tokens y chunks | ✅ | — |
| Calidad recuperación (golden, smoke) | ✅ | — |
| Cobertura por carpeta | ✅ | — |
| Tabla filtrable de documentos | ✅ (solo lectura) | acciones / review links de ingesta |
| Jobs / registry | ❌ | detalle pipeline interno |
| Live bar ingesta | ❌ | actividad Fase 0 en vivo |

---

## 7. Modo operacional en backend

Variable de entorno:

```env
MMI_DEPLOY_MODE=operational   # default local: development
```

Comportamiento cuando `operational`:

| Ruta / acción | Comportamiento |
|---------------|----------------|
| `GET /api/ingestion-results` | ✅ permitido |
| `GET /api/motor/health`, `/api/graph/health` | ✅ permitido |
| `POST /api/search`, `/api/ask`, `/api/motor/*` | ✅ permitido |
| `POST /api/ingestion-action` | ❌ 403 |
| `GET /api/ingestion-live` | ❌ 404 o snapshot estático |
| CORS `Access-Control-Allow-Origin` | Solo `https://mmi.monitoring.lat` |
| Generación landing | Catálogo operativo (sin sección ingesta dev) |

---

## 8. Sincronización local → VPS

La ingesta corre en local; el VPS necesita **datos de stats** actualizados y **índice en la nube** (Qdrant/Supabase ya compartidos).

### 8.1 Qué sincronizar (rsync / scp / CI)

| Archivo | Frecuencia | Uso web |
|---------|------------|---------|
| `out/ingestion-results.json` | Tras cada lote | Stats API + HTML |
| `out/analysis-status.json` | Tras cada lote | Tabla documentos (lectura) |
| `out/index-corpus-summary.json` | Tras indexación | Top docs por tokens |
| `out/golden-set-eval.json` | Tras evaluación | Métrica calidad en stats |
| `out/query-smoke.json` | Tras smoke | Badge "consultas OK" |

**No sincronizar:** `ocr-staging/`, manifests raw, herramientas de review, registry con jobs internos.

### 8.2 Script propuesto

```powershell
# local — tras cerrar un lote
.venv\Scripts\python -m mmi.tools.ingestion_results
scp out/ingestion-results.json out/analysis-status.json root@2.25.197.231:/opt/mmi/out/
ssh root@2.25.197.231 "systemctl reload mmi-api"
```

Automatizable con GitHub Action o n8n en el VPS.

---

## 9. Seguridad y privacidad

| Medida | Implementación |
|--------|----------------|
| No indexar | `robots.txt` Disallow `/` + `X-Robots-Tag: noindex, nofollow` |
| HTTPS | Let's Encrypt en nginx |
| Acceso sin perfiles | HTTP Basic Auth (equipo Monitoring + cliente autorizado) |
| API no expuesta directamente | Puerto 8773 solo localhost; nginx proxy `/api/` |
| Firewall | Abrir 443, 22; cerrar 8773, 5678 (n8n) al exterior o IP restrict |
| Secretos | `.env` en VPS; mismas keys Qdrant/Supabase/OpenRouter que local |
| Rate limit | nginx `limit_req` en `/api/ask` y `/api/motor/analyze` |
| Logs | Sin volcar prompts completos en logs de producción |

---

## 10. Fases de implementación

### Fase O1 — Rama y plan ✅
- [x] Rama `feature/mmi-operational-web`
- [x] Este documento

### Fase O2 — Vitrina (pruebas + ejemplos)
- [x] `src/mmi/web/vitrina.py` — landing + pruebas + ejemplos
- [x] `src/mmi/web/deploy_mode.py` — `MMI_DEPLOY_MODE=vitrina`
- [x] Nav vitrina en `review_shell.py`
- [x] CLI `python -m mmi.tools.vitrina`
- [x] `serve_local` bloquea `ingestion-action` en vitrina

### Fase O3 — Backend read-only
- [x] Bloqueo `ingestion-action` en modo vitrina
- [x] CORS cerrado en vitrina (mismo origen)
- [x] Health `/api/motor/health` + diag `/api/vitrina/diag`
- [x] Live queries controladas (`MMI_VITRINA_LIVE_QUERIES`)

### Fase O4 — Despliegue (Railway)

Guía: [`deploy/RAILWAY.md`](../deploy/RAILWAY.md) · alternativa VPS: [`deploy/VPS-N8N.md`](../deploy/VPS-N8N.md)

- [x] `Dockerfile` (raíz) + `entrypoint.sh` + `railway.toml`
- [x] Seed JSON de pruebas en imagen
- [x] Demo abierta por defecto (`MMI_VITRINA_OPEN=1`)
- [ ] DNS `mmi.monitoring.lat` → Railway
- [ ] Sync stats local → seed/volumen (post-lote)

### Fase O5 — Copy y guía de uso
- [x] Landing: vitrina de ingesta, pruebas, ejemplos, guía
- [x] Explicaciones de métricas en `/pruebas.html`
- [x] “Analizando…” en ejemplos / search / rag
- [ ] Validación con usuario piloto

### Fase O6 — (Futuro) Perfiles
- Supabase Auth o SSO Monitoring
- Auditoría de consultas por usuario
- Basic Auth opcional si se cierra la demo (`MMI_VITRINA_OPEN=0`)

---

## 11. Criterios de aceptación

| # | Criterio |
|---|----------|
| A1 | Landing con 2 tarjetas: Pruebas + Ejemplos (sin panel de carga) |
| A2 | `/pruebas.html` muestra smoke, golden y validación RAG |
| A3 | `/ejemplos.html` enlaza consultas predefinidas del corpus |
| A4 | search/rag responden contra índice en nube |
| A5 | Sin enlaces a review, ingesta admin ni tabla completa de docs |
| A6 | `robots.txt` + headers bloquean indexación |
| A7 | Demo abierta o Basic Auth opcional (`MMI_VITRINA_OPEN`) |
| A8 | Ingesta local no se ve afectada; sync es unidireccional |
| A9 | Copy: “vitrina de ingesta” / ingesta interna Monitoring |

---

## 12. Decisiones abiertas

| # | Pregunta | Opciones |
|---|----------|----------|
| D1 | ¿Mapa en v1 operativa? | Sí / No / Solo lectura sin graph ask |
| D2 | ¿Demo comercial `app.html` en subruta? | `/demo` privado / omitir en v1 |
| D3 | ¿Basic Auth global o solo `/api/`? | Global recomendado |
| D4 | ¿Frecuencia sync stats? | Manual / semanal / post-lote |
| D5 | ¿Multi-corpus en web? | Un solo tenant `monitoring` en v1 |

---

## 13. Referencia rápida API (modo operativo)

```http
GET  /api/motor/health
GET  /api/ingestion-results

POST /api/search          { "query": "…", "limit": 8 }
POST /api/ask             { "query": "…", "limit": 6 }
POST /api/ask-details     { "ask_id": "…", "section": "sources" }
POST /api/motor/analyze   { "asset_id": "…", "symptom": "…", "window": "24h" }
POST /api/motor/details   { "motor_id": "…", "section": "sources" }
```

---

*Documento vivo — actualizar al cerrar cada fase O.*
