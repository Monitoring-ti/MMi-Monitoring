# Vitrina MMI — cierre de etapa y despliegue

Web pública **solo lectura + consultas**: dashboard, pruebas estáticas, ejemplos, búsqueda y RAG.  
**No** incluye ingesta, review, motor ni mapa en el sitio.

Dominio objetivo: `https://mmi.monitoring.lat` · VPS: ver [`VPS-N8N.md`](VPS-N8N.md)

---

## 1. Qué subir (alcance de esta etapa)

| Incluir | Excluir de este deploy |
|---------|-------------------------|
| `src/mmi/web/` · `search_page.py` · `vitrina_examples.py` | `app/` · `lib/` · Next.js |
| `src/mmi/tools/vitrina.py` · `serve_local.py` · `search_cli.py` | Portal dev / landing operativa |
| `src/mmi/search/rag_page.py` · `review_shell.py` | Ingesta en VPS |
| `deploy/` · `scripts/publish_vitrina.ps1` | `out/` en git (se sincroniza por SCP) |
| `public/monitoring-logo-*.svg` · logos actualizados | Secretos `.env` |

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

## 3. Publicar al VPS

Script todo-en-uno (desde Windows):

```powershell
.\scripts\publish_vitrina.ps1 -Host root@2.25.197.231 -RemoteDir /opt/mmi
```

Manual:

```powershell
# 1) Código
git push origin feature/mmi-operational-web
ssh root@2.25.197.231 "cd /opt/mmi && git fetch && git checkout feature/mmi-operational-web && git pull && .venv/bin/pip install -e ."

# 2) JSON de pruebas + corpus (desde local)
scp out/query-smoke.json out/golden-set-eval.json out/rag-validation.json `
    out/load-test-report.json out/analysis-status.json out/ingestion-results.json `
    root@2.25.197.231:/opt/mmi/out/

# 3) Logos
scp public/monitoring-logo-horizontal.svg public/monitoring-logo-circular.svg `
    root@2.25.197.231:/opt/mmi/public/

# 4) Regenerar vitrina en el servidor
ssh root@2.25.197.231 @"
cd /opt/mmi
export MMI_DEPLOY_MODE=vitrina
.venv/bin/python -m mmi.tools.vitrina
systemctl restart mmi-api
"@

# 5) Comprobar
curl -s -u USUARIO:CLAVE https://mmi.monitoring.lat/api/motor/health
curl -s -u USUARIO:CLAVE -o /dev/null -w "%{http_code}" https://mmi.monitoring.lat/search.html
```

---

## 4. `.env` en producción (VPS)

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

systemd: descomentar / fijar `MMI_DEPLOY_MODE=vitrina` en `mmi-api.service` (ver `VPS-N8N.md` §6).

---

## 5. Checklist de cierre

- [ ] Logos en `public/` actualizados
- [ ] `python -m mmi.tools.vitrina` sin errores
- [ ] Links internos OK (`verify_vitrina_links.py`)
- [ ] Rama pusheada · VPS en `feature/mmi-operational-web`
- [ ] JSON de pruebas en `/opt/mmi/out/`
- [ ] `MMI_DEPLOY_MODE=vitrina` en VPS
- [ ] nginx Basic Auth activo
- [ ] `/robots.txt` → `Disallow: /`
- [ ] n8n intacto (`docker ps | grep n8n`)

---

## 6. Actualizar resultados (sin redeploy de código)

Tras nuevas pruebas locales:

```powershell
.venv\Scripts\python -m mmi.tools.query_smoke    # si aplica
$env:MMI_DEPLOY_MODE = "vitrina"
.venv\Scripts\python -m mmi.tools.vitrina
.\scripts\publish_vitrina.ps1 -Host root@2.25.197.231 -JsonOnly
```
