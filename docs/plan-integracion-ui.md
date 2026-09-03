# Integración UI — Monorepo MMI (APARCADA para vitrina)

**Fecha:** 2026-09-02 · **Actualizado:** 2026-09-03  
**Estado:** ⏸️ **Aparcada** — no forma parte de la vitrina pública `mmi.monitoring.lat`  
**Vitrina vigente:** [`plan-mmi-operational-web.md`](plan-mmi-operational-web.md) (HTML + Railway)

La idea Next.js ↔ Motor MMI queda documentada aquí por si se retoma como **producto comercial aparte**.  
La vitrina v1 sigue el plan original: Inicio · Pruebas · Ejemplos · Búsqueda · RAG (sin Next).

---

## 1. Arquitectura unificada

El monorepo combina **dos capas de presentación** sobre **un solo backend Python**:

```
┌─────────────────────────────────────────────────────────────────┐
│  CAPA COMERCIAL (Next.js :3000)                                 │
│  app/page.tsx — landing + demo embebida                         │
│  Flujo: Overview → Loading → Diagnostic → Final                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │ proxy /api/*  (next.config rewrites)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  API MMI (Python serve_local :8773)                             │
│  POST /api/motor/analyze   — diagnóstico activo + síntoma       │
│  POST /api/motor/details   — fuentes, EAM, discrepancias        │
│  POST /api/ask             — RAG con citas                      │
│  POST /api/graph/*         — mapa de conocimiento                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   Qdrant híbrido      Supabase/pg        OpenRouter
   (dense + BM25)      (metadatos)        (generación)
```

**UI técnica legacy** (mismo backend, sin Next.js):

| Pantalla | URL | Uso |
|----------|-----|-----|
| Motor MMI | `/motor.html` | Operadores / validación corpus |
| Búsqueda | `/search.html` | Retrieval puro |
| RAG | `/rag.html` | Pregunta + citas |
| Mapa | `/mapa.html` | Grafo relacional |
| Calidad datos | `/data-quality.html` | Dashboard Fase D |
| Revisión | `/review.html` | Hub ingesta |

---

## 2. Flujo de diagnóstico (demo comercial)

Las pantallas HTML que compartiste se mapean así:

| Pantalla HTML | Vista React | API |
|---------------|-------------|-----|
| Panel de Control Inicial | `Overview` | — (KPIs ilustrativos) |
| Análisis en Progreso | `LoadingView` | espera `motor/analyze` |
| Diagnostic Workspace | `Diagnostic` | `motor/analyze` + `motor/details` |
| Resultado Final | `FinalView` | datos de sesión + validación humana |

### Secuencia

1. Usuario elige **activo** (`CTS-DCH-ENF`, `MRI-ODS21`, `STG-01-X`) y escribe **síntoma**.
2. `POST /api/motor/analyze` → búsqueda híbrida + LLM estructurado.
3. Respuesta JSON: `verified_facts`, `hypotheses`, `physical_checks`, `discrepancies`.
4. Panel derecho: `POST /api/motor/details` sección `sources`.
5. Validación humana → vista certificado (`FinalView`).

Si la API no responde, la demo cae a **fixture local** (`DEMO_FALLBACK`) con aviso visible.

---

## 3. Arranque local (dos terminales)

```powershell
# Terminal 1 — Backend
cd mmi-by-monitoring
.venv\Scripts\activate
pip install -e .
.venv\Scripts\python -m mmi.tools.serve_local --port 8773

# Terminal 2 — Frontend comercial
npm install
npm run dev
# → http://localhost:3000#demo
```

Health check:

```powershell
curl http://127.0.0.1:8773/api/motor/health
# {"ok": true, "motor_api": true, "version": "m6"}
```

---

## 4. Archivos clave

| Ruta | Rol |
|------|-----|
| `lib/mmi-api.ts` | Cliente TypeScript + tipos Motor |
| `app/page.tsx` | Landing comercial + `DemoApp` conectada |
| `next.config.ts` | Proxy `/api/*` → `:8773` |
| `src/mmi/tools/api_routes.py` | Rutas compartidas backend |
| `src/mmi/motor/analyze.py` | Lógica diagnóstico |
| `fixtures/motor-demo.json` | Fixture alineado con demo |

Variable opcional:

```env
MMI_API_URL=http://127.0.0.1:8773
```

---

## 5. Próximos pasos (backlog)

| # | Tarea | Prioridad |
|---|-------|-----------|
| I1 | KPIs Overview desde `analysis-status.json` | media |
| I2 | Enlace directo a `mapa.html` / `data-quality.html` desde sidebar | baja |
| I3 | Auth + tenant (Fase 3 producto) | alta (prod) |
| I4 | Unificar estilos HTML legacy → componentes React | baja |
| I5 | WebSocket progreso real en `LoadingView` | media |

---

## 6. Decisiones de diseño

- **Monorepo, dos servidores en dev:** Python sirve API + HTML técnico; Next.js sirve presentación comercial. El proxy evita CORS en desarrollo.
- **Misma API que `motor.html`:** la demo comercial no duplica lógica; consume los mismos endpoints.
- **Validación humana obligatoria:** el botón «Validar diagnóstico» es gate de UI; no persiste en DB aún (Fase 3).
