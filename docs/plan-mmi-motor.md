# Motor MMI — Plan de consulta por activo y síntoma

**Fecha:** 2026-09-01  
**Estado:** ✅ M1–M6 cerrados · Motor MMI piloto completo  
**Precondiciones:** ✅ RAG validado · ✅ B4 catálogo EAM 100%  
**Objetivo:** evolucionar de “buscar/preguntar documentos” a **consultar un activo con síntoma**, obteniendo diagnóstico estructurado, evidencia verificable, hipótesis rankeadas y acciones de verificación física — siempre con citas trazables.

**Relacionado:** [`plan.md`](plan.md) Fase 2 · [`plan-fase-b.md`](plan-fase-b.md) B4 catálogo EAM · [`plan-fase-c.md`](plan-fase-c.md) C2 contradicciones

---

## 1. Visión de producto

### Hoy (MVP Fase 2)

| Pantalla | Qué hace |
|----------|----------|
| `search.html` | Fragmentos híbridos (Qdrant + BM25) |
| `rag.html` | Respuesta redactada + referencias + evidencia |

El usuario debe formular la pregunta y conocer códigos documentales (GUIGS, FMECA, etc.).

### Objetivo Motor MMI

Pantalla **`motor.html`** — “Consultar motor MMI”:

```
┌─────────────────────────────────────────────────────────────────┐
│ Consultar motor MMI                                              │
├─────────────────────────────────────────────────────────────────┤
│ [ Alta temperatura y vibración en turbina STG-01-X          ]    │
│ Activo: [ STG-01-X ▼ ]   Vigencia: [ Últimas 24 h ▼ ]  [Analizar]│
└─────────────────────────────────────────────────────────────────┘

┌─ Análisis generado ─────────────────────────────────────────────┐
│ Diagnóstico del síntoma          │ Evidencia soportada           │
│                                  │ Confianza alta · 92%          │
│                                  │ Hechos verificados            │
│                                  │ (datos + documentos)          │
│  … texto estructurado …          │ • TE-401A 98 °C (lím 95)      │
│                                  │   Manual OEM GE · Vol.2 p.112 │
│                                  │ • VE-402X 5,2 mm/s RMS 1X RPM │
│                                  │   Manual OEM GE · Vol.3 p.45  │
│                                  │ • FT-405 120 L/min (nom 150)  │
│                                  │   P&ID Lubricación · Rev.4    │
├──────────────────────────────────┴──────────────────────────────┤
│ Hipótesis del sistema                                           │
│ Inferencia IA: requiere criterio del especialista               │
│  H1 Desalineamiento térmico rotor–estator          92%          │
│  H2 Falla suministro aceite lubricante             68%          │
├─────────────────────────────────────────────────────────────────┤
│ Verificación física                          [ Exportar PDF ]     │
│  ☐ Verificar nivel/presión tanque LSH-400                       │
│  ☐ Muestra aceite ISO 4406 urgente                              │
│  ☐ Inspeccionar termocupla TE-401A (falso contacto / vaina)     │
├─────────────────────────────────────────────────────────────────┤
│ Fuentes y evidencia                                             │
│  [Manual OEM GE Frame 6B · Vol.2 p.112]  [Histórico EAM WO-88912]│
│  … snippet documento …              … WO causa / MTBF …           │
├─────────────────────────────────────────────────────────────────┤
│ ⚠ Discrepancia detectada                                        │
│ PT-882 calibrado hace >365 días; lectura ±5%                    │
└─────────────────────────────────────────────────────────────────┘
```

**Principio:** cada afirmación numérica o causal debe enlazar a **fuente** (chunk documental, tag PI/EAM, WO CMMS) o marcarse como **inferencia** con confianza explícita.

---

## 2. Caso de uso de referencia (ODS1)

| Campo | Ejemplo mock | Fuente real en corpus ODS1 |
|-------|--------------|----------------------------|
| Activo | `STG-01-X` | `catalog_assets` (B4) + tags en chunks |
| Síntoma | Alta T° + vibración turbina | Texto libre del operador |
| Sensores | TE-401A, VE-402X, FT-405 | Integración futura PI/SCADA o CSV fixture |
| Manuales | Manual OEM GE Vol. 2/3 | `manual_oem` indexados (4400285992-…) |
| P&ID | Lubricación Rev. 4 | `plano` / diagramas en corpus |
| Histórico | WO-88912, MTBF 8400 h | EAM/CMMS vía B4 o API stub |
| Discrepancia | Calibración PT-882 >365 d | Reglas metrología + metadatos instrumento |

El mock usa turbina STG; en ODS1 el piloto natural es **sistema de enfriamiento / equipos eléctricos** (ATM, matrices MRI, FMECA anexos) hasta conectar PI real.

---

## 3. Relación con lo ya construido

| Capa existente | Reutilización en Motor MMI |
|----------------|----------------------------|
| `HybridSearchEngine` | Recuperación por síntoma + activo + tags |
| `/api/ask` + sesión | Base de generación; extender payload |
| `rag.html` | Patrón UI respuesta + refs + evidencia |
| `review.html` / identidad B1 | Solo documentos `active` / vigentes |
| `catalog_assets` (SQL B4) | Validación código activo, área, criticidad |
| `chunk_metadata` | Filtro `asset_codes`, `criticality_level` |
| Fase C C2 | Bloque “Discrepancia detectada” (versiones / conflictos) |
| Fase C C3 | Golden set incluye consultas por síntoma |

**No reimplementar:** chunking, embeddings, nav unificada (`review_shell`), lazy-load referencias.

---

## 4. Arquitectura propuesta

```
Entrada UI (motor.html)
  → activo + vigencia + síntoma
       ↓
POST /api/motor/analyze
  ├─ 1. Resolver activo (catalog_assets)
  ├─ 2. Contexto temporal (PI/EAM/CMMS o fixture)
  ├─ 3. Recuperación híbrida filtrada (activo, tipo doc, vigencia)
  ├─ 4. Extracción hechos verificados (structured output LLM)
  ├─ 5. Generación hipótesis H1..Hn + score confianza
  ├─ 6. Checklist verificación física (accionable)
  ├─ 7. Detección discrepancias (calibración, versión doc, dato vs límite OEM)
  └─ 8. Persistir sesión motor_id (refs, evidencia, export PDF)
       ↓
Respuesta JSON → motor.html (layout diagnóstico)
```

### Fuentes de datos (por fase)

| Fuente | Fase piloto | Producción |
|--------|-------------|------------|
| Documentos indexados | ✅ inmediato | ✅ |
| Catálogo activos (B4) | fixture JSON | Supabase `catalog_assets` |
| Histórico CMMS | fixture WO | API EAM |
| Tags PI / time series | CSV demo o mock | PI Web API / OPC-UA |
| Metrología / calibración | reglas en prompt + tabla stub | CMMS calibraciones |

---

## 5. Bloques de entrega

### M1 — UI Consultar motor (shell) ✅

| Tarea | Estado |
|-------|--------|
| M1.1 | `motor.html` + nav “Motor MMI” en `review_shell` | ✅ |
| M1.2 | Formulario: síntoma, selector activo, vigencia | ✅ |
| M1.3 | Layout análisis: diagnóstico · hechos · hipótesis · verificación · fuentes · discrepancias | ✅ |
| M1.4 | Estados: vacío · cargando · resultado · error | ✅ |
| M1.5 | Deep link `motor.html?asset=…&q=…` | ✅ |

**Archivos:** `src/mmi/motor/page.py` · `fixtures/motor-demo.json`

**DoD M1:** UI estática con datos fixture ODS1 (enfriamiento CTS DCH); sin backend aún.

### M2 — API análisis estructurado ✅

| Tarea | Estado |
|-------|--------|
| M2.1 | `POST /api/motor/analyze` — `{ asset_id, symptom, window }` | ✅ |
| M2.2 | Schema respuesta (ver §6) | ✅ |
| M2.3 | `MotorSessionStore` (análogo `AskSessionStore`) | ✅ |
| M2.4 | `POST /api/motor/details` — fuentes ampliadas bajo demanda | ✅ |
| M2.5 | Prompt plantilla: hecho vs hipótesis vs acción | ✅ |

**Archivos:** `src/mmi/motor/analyze.py` · `session.py` · `payloads.py` · `serve_local.py`

**DoD M2:** respuesta JSON válida contra corpus ODS1; citas en hechos verificados.

### M3 — Hechos verificados (datos + documentos) ✅

| Tarea | Estado |
|-------|--------|
| M3.1 | Parser límites OEM desde chunks (regex + guardrail) | ✅ |
| M3.2 | Adapter lecturas sensor (fixture → PI) con unidad y timestamp | ✅ |
| M3.3 | Tarjeta “Hecho verificado”: valor medido · límite · fuente documento/página | ✅ |
| M3.4 | Badge confianza agregada (nº fuentes, acuerdo doc-dato) | ✅ |

**Archivos:** `oem_limits.py` · `sensors.py` · `verified_facts.py` · `fixtures/motor-sensors.json`

**DoD:** caso mock TE-401A/VE-402X/FT-405 reproducible con fixture CTS-DCH-ENF.

### M4 — Hipótesis del sistema ✅

| Tarea | Estado |
|-------|--------|
| M4.1 | Generar H1..H3 con `%` confianza y justificación breve | ✅ |
| M4.2 | Etiqueta obligatoria: “Inferencia IA — requiere criterio del especialista” | ✅ |
| M4.3 | Vincular cada hipótesis a hechos que la soportan | ✅ |
| M4.4 | No presentar hipótesis como hechos (validación schema) | ✅ |

**Archivos:** `hypotheses.py` · `page.py` (UI hechos soportados)

**DoD:** ≥2 hipótesis rankeadas en piloto CTS-DCH-ENF con `supported_facts`.

### M5 — Verificación física y export ✅

| Tarea | Estado |
|-------|--------|
| M5.1 | Lista acciones checkbox (copiar / export) | ✅ |
| M5.2 | Priorización urgente / rutina (criticidad + alarma) | ✅ |
| M5.3 | Print CSS client-side (`window.print`) | ✅ |
| M5.4 | Pie de página: activo, timestamp, modelo LLM, ids fuente | ✅ |

**Archivos:** `physical_checks.py` · `export_meta.py` · `page.py` (print CSS)

**DoD:** PDF exportable vía imprimir con hechos + hipótesis + checklist + referencias.

### M6 — Discrepancias y histórico EAM ✅

| Tarea | Estado |
|-------|--------|
| M6.1 | Regla calibración vencida (días desde última calibración) | ✅ |
| M6.2 | Panel histórico WO (código, fecha, causa, MTBF vs esperado) | ✅ |
| M6.3 | Contradicciones C2 stub: doc vigente vs lectura / vs WO previo | ✅ |
| M6.4 | Banner “Discrepancia detectada” no bloqueante | ✅ |

**Archivos:** `discrepancies.py` · `eam_history.py` · `fixtures/motor-eam.json` · `fixtures/motor-discrepancies.json`

**DoD:** mock PT-882 + WO-88912 visibles; reglas extensibles en JSON.

---

## 6. Contrato API (borrador)

### `POST /api/motor/analyze`

**Request**

```json
{
  "asset_id": "STG-01-X",
  "symptom": "Alta temperatura y vibración en turbina",
  "window": "24h",
  "limit": 10
}
```

**Response**

```json
{
  "motor_id": "abc123",
  "asset": { "id": "STG-01-X", "name": "Turbina STG-01-X", "criticality": "A" },
  "symptom": "...",
  "window": "24h",
  "diagnosis": { "summary": "...", "confidence_label": "alta", "confidence_pct": 92 },
  "verified_facts": [
    {
      "text": "Temperatura cojinete TE-401A: 98 °C (límite 95 °C)",
      "kind": "measurement",
      "citation_index": 1,
      "source": { "type": "document", "citation": "Manual OEM GE · Vol. 2 · p. 112" }
    }
  ],
  "hypotheses": [
    {
      "id": "H1",
      "title": "Desalineamiento térmico rotor–estator",
      "rationale": "...",
      "confidence_pct": 92,
      "supported_fact_indices": [1, 2]
    }
  ],
  "physical_checks": [
    { "text": "Verificar nivel y presión tanque LSH-400", "priority": "urgent" }
  ],
  "discrepancies": [
    { "text": "PT-882 calibrado hace >365 días; ±5%", "severity": "warn" }
  ],
  "sources_preview": [ "..." ],
  "model": "openai/gpt-4o-mini",
  "elapsed_ms": 4200
}
```

### `POST /api/motor/details`

Secciones: `sources` · `eam_history` · `raw_evidence` · `discrepancies_full`

---

## 7. Modelo de confianza (reglas MVP)

| Nivel | Criterio |
|-------|----------|
| **Alta (≥85%)** | ≥2 hechos convergentes + cita documental OEM/norma + dato dentro de ventana |
| **Media (60–84%)** | 1 hecho fuerte + inferencia coherente sin contradicción C2 |
| **Baja (<60%)** | Solo inferencia o fuente única no metrología |

Mostrar siempre el porcentaje por hipótesis; nunca ocultar que H1–Hn son inferencias.

---

## 8. Integración en roadmap

### Orden sugerido (después de validar RAG)

| Sprint | Entregable |
|--------|------------|
| **M-sprint 1** | M1 UI fixture + M2 API schema stub |
| **M-sprint 2** | M3 hechos verificados (docs ODS1) + enlace desde `rag.html` |
| **M-sprint 3** | M4 hipótesis + M5 export PDF |
| **M-sprint 4** | M6 discrepancias + B4 catálogo activos real |
| **M-sprint 5** | PI/EAM live (fuera MVP documental) |

### Dependencias

| Dep | Bloque | Por qué |
|-----|--------|---------|
| B4 | Catálogo EAM | Selector activo autorizado |
| C2 | Contradicciones | Discrepancias doc vs doc |
| C3 | Golden set | Evaluar consultas síntoma |
| B2 | Cola | Re-index al conectar nuevas fuentes PI |

### Impacto en recorte MVP (`plan.md`)

El MVP documental **sigue sin agentes autónomos ni n8n**. Motor MMI es **asistido**: el especialista dispara el análisis, revisa hipótesis y ejecuta verificación física manualmente.

---

## 9. Archivos previstos

| Archivo | Rol |
|---------|-----|
| `src/mmi/motor/analyze.py` | Orquestación análisis |
| `src/mmi/motor/schema.py` | Tipos + validación respuesta |
| `src/mmi/motor/fixtures/` | STG-01-X demo + ODS1 enfriamiento |
| `src/mmi/motor/prompts.py` | Plantillas hechos / hipótesis |
| `src/mmi/search/motor_page.py` | HTML `motor.html` |
| `src/mmi/tools/serve_local.py` | Rutas `/api/motor/*` |
| `docs/plan-mmi-motor.md` | Este documento |

---

## 10. Criterios de aceptación (piloto)

- [ ] Operador selecciona activo y describe síntoma en ≤30 s.
- [ ] Análisis muestra ≥3 hechos verificados con cita clicable.
- [ ] ≥2 hipótesis con % y disclaimer de inferencia.
- [ ] Checklist ≥3 acciones de verificación física.
- [ ] ≥1 discrepancia o histórico EAM cuando aplique fixture.
- [ ] Export PDF incluye trazabilidad (fuentes + timestamp).
- [ ] Sin afirmaciones normativas sin documento `active` citado.

---

## 11. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Alucinación en hipótesis | Schema estricto; hechos separados; disclaimer UI |
| Activos no en catálogo | Modo “activo libre” deshabilitado en prod |
| PI no disponible | Fixtures + adapter interface |
| Confusión RAG vs Motor | Nav separada; `rag.html` = preguntas abiertas; `motor.html` = activo+síntoma |
| PDF sin mantenimiento | Print CSS primero; PDF server después |

---

## 12. Enlaces UI (objetivo)

| Página | URL |
|--------|-----|
| Motor MMI | http://127.0.0.1:8773/motor.html |
| Consulta RAG | http://127.0.0.1:8773/rag.html |
| Búsqueda | http://127.0.0.1:8773/search.html |
| Revisión | http://127.0.0.1:8773/review.html |
