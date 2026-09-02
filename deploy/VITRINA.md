# Vitrina MMI — cierre de etapa y despliegue

Web pública **solo lectura + consultas**: dashboard, pruebas estáticas, ejemplos, búsqueda y RAG.  
**No** incluye ingesta, review, motor ni mapa en el sitio.

**Camino principal:** [Railway](RAILWAY.md) · Alternativa VPS: [VPS-N8N.md](VPS-N8N.md)

Dominio objetivo: `https://mmi.monitoring.lat`

---

## 1. Qué subir (alcance de esta etapa)

| Incluir | Excluir de este deploy |
|---------|-------------------------|
| `src/mmi/web/` · `search_page.py` · `vitrina_examples.py` | `app/` · `lib/` · Next.js |
| `src/mmi/tools/vitrina.py` · `serve_local.py` · `search_cli.py` | Portal dev / landing operativa |
| `src/mmi/search/rag_page.py` · `review_shell.py` | Ingesta en el servidor |
| `deploy/` · `railway.toml` · `deploy/railway-seed/` | Secretos `.env` |
| `public/monitoring-logo-*.svg` | |

---

## 2. Build local (antes de subir)

```powershell
cd mmi-by-monitoring
$env:MMI_DEPLOY_MODE = "vitrina"
.venv\Scripts\python -m mmi.tools.vitrina
.venv\Scripts\python scripts\verify_vitrina_links.py   # requiere serve_local en :8773
```

Páginas generadas en `out/`:

- `/` · `/pruebas.html` · `/ejemplos.html` · `/search.html` · `/rag.html` · `/robots.txt`

---

## 3. Publicar — Railway (recomendado)

Guía completa: [`RAILWAY.md`](RAILWAY.md)

```powershell
# Actualizar seed de métricas + push
Copy-Item out\query-smoke.json,out\golden-set-eval.json,out\rag-validation.json,out\load-test-report.json,out\analysis-status.json,out\ingestion-results.json deploy\railway-seed\ -Force
git push origin feature/mmi-operational-web
```

En Railway: deploy desde GitHub · vars Qdrant/Supabase/OpenRouter · `MMI_DEPLOY_MODE=vitrina` · custom domain `mmi.monitoring.lat`.

---

## 4. Alternativa — VPS Hostinger

Script: `.\scripts\publish_vitrina.ps1 -Host root@2.25.197.231`  
Detalle: [`VPS-N8N.md`](VPS-N8N.md)

---

## 5. `.env` en producción

```env
MMI_DEPLOY_MODE=vitrina

QDRANT_URL=...
QDRANT_API_KEY=...
QDRANT_COLLECTION=mmi_chunks
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o-mini
```

---

## 6. Checklist de cierre

- [ ] Logos en `public/` actualizados
- [ ] `python -m mmi.tools.vitrina` sin errores
- [ ] Seed JSON en `deploy/railway-seed/`
- [ ] Servicio Railway healthy (`/api/motor/health`)
- [ ] DNS `mmi.monitoring.lat` → Railway
- [ ] Auth (Cloudflare Access o equivalente)
- [ ] `/robots.txt` → `Disallow: /`
