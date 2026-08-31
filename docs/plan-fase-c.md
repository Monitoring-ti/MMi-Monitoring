# Fase C — Plan operativo MMI (post Fase B)

**Fecha:** 2026-08-31  
**Precondición:** Fase B completada (cola, PPTX, catálogo, dashboard)  
**Objetivo:** calidad de recuperación, extracción con incertidumbre (OCR), y detección de conflictos — sin mezclar con deuda de ingesta B.

---

## 1. Bloques Fase C

| Bloque | Nombre | Entregable principal |
|--------|--------|----------------------|
| **C1** | Reranker post-filtro | Mejor orden tras dense+BM25 |
| **C2** | Contradicciones multi-versión | Alertas diapositivas/docs vigentes en conflicto |
| **C3** | Golden set + eval | Recall/precision por tipo documental |
| **C4** | OCR con incertidumbre | [`plan-fase-c-ocr.md`](plan-fase-c-ocr.md) |
| **C5** | Cola async (opcional) | Redis / Supabase Realtime si volumen crece |

**Especificaciones detalladas:**

- OCR: [`docs/plan-fase-c-ocr.md`](plan-fase-c-ocr.md)
- PPTX (Fase B, prerequisito visual): [`docs/plan-pptx-extraction.md`](plan-pptx-extraction.md)

---

## 2. C4 — OCR (resumen)

Principio: **no almacenar solo “lo que leyó”**, sino dónde, con qué confianza, desde qué imagen y qué validaciones se aplicaron.

```
original → hash → preprocess → OCR/página → estructura espacial
         → crudo + normalizado + validación → chunk → embed → activate
```

Capas obligatorias: imagen original, preprocesada, texto crudo, normalizado, bbox, confianza, correcciones auditables.

**Piloto:** `IFC-078` (lote 1, `phase0=ocr`).

Ver checklist completo en `plan-fase-c-ocr.md` §11.

---

## 3. C1 — Reranker

| Tarea | Detalle |
|-------|---------|
| C1.1 | Reranker cross-encoder o API (Cohere / local) tras top-k híbrido |
| C1.2 | Boost adicional tags exactos post-rerank |
| C1.3 | Métricas en golden set (C3) |

**DoD:** +5% recall@5 en golden set vs baseline híbrido.

---

## 4. C2 — Contradicciones

| Tarea | Detalle |
|-------|---------|
| C2.1 | Detectar chunks `active` con mismo `document_key` y contenido semántico conflictivo |
| C2.2 | PPTX: diapositivas vigentes con RPN/criticidad distinta |
| C2.3 | API `/api/ask` devuelve bloque `conflictos` para validación humana |

**DoD:** caso GUIGS Rev 6 vs fragmento superseded no aparece; conflicto real se muestra explícitamente.

---

## 5. C3 — Golden set y evaluación

| Tarea | Detalle |
|-------|---------|
| C3.1 | 30–50 consultas anotadas por tipo (norma, guía, tabla, presentación, plano) |
| C3.2 | Script `tools/eval_retrieval.py` — recall@k, MRR |
| C3.3 | CI opcional en PR |

---

## 6. Orden de implementación (sprints)

### Sprint C1 — OCR piloto (1–2 semanas)

1. Migración `003_ocr_schema.sql`
2. C4.1–C4.8 modelos + Azure adapter + store
3. C4.9 PDF híbrido + `process_manifest` para IFC-078
4. C4.10–C4.12 chunking + worker + UI revisión

### Sprint C2 — OCR producción + PPTX visual (1 semana)

1. C4.13 indexar IFC-078
2. C4.14 PPTX regiones → OCR selectivo
3. Reglas validación EAM en `ocr_validate.py`

### Sprint C3 — Calidad búsqueda (1 semana)

1. C3 golden set
2. C1 reranker
3. Métricas baseline

### Sprint C4 — Conflictos + escala (opcional)

1. C2 detección conflictos
2. C5 cola async si necesario

---

## 7. Checklist Fase C

### OCR (C4)
- [ ] Capas crudo + normalizado preservadas
- [ ] IFC-078 indexado con citas página/región
- [ ] Re-OCR incremental por página
- [ ] UI diff crudo ↔ normalizado

### Búsqueda (C1–C3)
- [ ] Reranker activo en `/api/search`
- [ ] Golden set con recall documentado
- [ ] Sin corrección silenciosa de códigos técnicos

### Gobernanza (C2)
- [ ] Conflictos multi-versión visibles en respuesta
- [ ] Solo `validation_status=pass` en producción por defecto

---

## 8. Referencias

- Fase B: `docs/plan-fase-b.md`
- OCR detallado: `docs/plan-fase-c-ocr.md`
- PPTX: `docs/plan-pptx-extraction.md`
- Ingesta: `docs/plan-ingesta.md`
- MVP: `docs/plan.md`
