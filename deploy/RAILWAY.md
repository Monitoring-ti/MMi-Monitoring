# Railway — despliegue vitrina MMI

Un solo servicio: HTML (dashboard / pruebas / ejemplos / búsqueda / RAG) + API.

Dominio: `mmi.monitoring.lat` → CNAME al dominio Railway (o custom domain en el dashboard).

---

## 1. Crear el proyecto

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
2. Repo: `Monitoring-ti/MMi-Monitoring` · rama `feature/mmi-operational-web` (o `main` tras merge)
3. **Root Directory:** vacío (raíz del repo)
4. Railway debe usar el **`Dockerfile`** de la raíz (`railway.toml` → `builder = "DOCKERFILE"`)

Si Railway muestra **Railpack** (“No start command detected”):

1. Servicio → **Settings → Build**
2. **Builder:** `Dockerfile` (no Railpack / Nixpacks)
3. **Dockerfile path:** `Dockerfile`
4. Redeploy

Start command (solo si hace falta): `/app/deploy/entrypoint.sh`
---

## 2. Variables de entorno

En el servicio → **Variables** (nunca en el repo):

```env
MMI_DEPLOY_MODE=vitrina

QDRANT_URL=https://...
QDRANT_API_KEY=...
QDRANT_COLLECTION=mmi_chunks

SUPABASE_URL=https://...
SUPABASE_SERVICE_ROLE_KEY=...

OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o-mini
```

`PORT` lo inyecta Railway solo — no lo fijéis.

Opcional:

```env
MMI_BIND_HOST=0.0.0.0
```

---

## 3. Dominio y HTTPS

1. Settings → **Networking** → **Generate Domain** → `*.up.railway.app`
2. **Custom Domain** → `mmi.monitoring.lat`
3. En Hostinger DNS:

| Tipo | Nombre | Valor |
|------|--------|-------|
| **CNAME** | `mmi` | el hostname que indique Railway (ej. `xxx.up.railway.app`) |

Railway gestiona el certificado TLS.

---

## 4. Auth y bloqueo de corpus (obligatorio)

La vitrina **no debe** quedar pública con `/api/search` y `/api/ask` abiertos.

### 4.1 Acceso (demo abierta)

Por defecto la vitrina va **sin login** (`MMI_VITRINA_OPEN=1`) y con consultas al corpus activas:

```env
MMI_VITRINA_OPEN=1
MMI_VITRINA_LIVE_QUERIES=1
```

Para cerrar de nuevo con Basic Auth:

```env
MMI_VITRINA_OPEN=0
MMI_BASIC_AUTH_USER=...
MMI_BASIC_AUTH_PASSWORD=...
MMI_VITRINA_LIVE_QUERIES=1
```

`/api/motor/health` queda libre para el healthcheck.

### 4.2 Consultas al corpus

| Valor `MMI_VITRINA_LIVE_QUERIES` | Efecto |
|-------|--------|
| `1` (default Railway demo) | `/api/search`, `/api/ask`, `/api/ask-details` activos |
| `0` | Consultas → **403** |

### 4.3 Auth por usuario / empresa / corpus

Basic Auth es opcional (capa 0). Autorización por tenant/empresa/corpus es **capa 1** — pendiente en roadmap.

### 4.4 Revisar logs (consultas ya hechas)

En Railway → servicio → **Logs** / **Observability**:

1. Filtrar `POST /api/search` y `POST /api/ask`
2. Anotar IPs/timestamps si hubo tráfico externo
3. Si hubo abuso: rotar `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, y opcionalmente API keys Qdrant/Supabase

### 4.5 Cloudflare Access (recomendado a medio plazo)

Dominio `mmi.monitoring.lat` detrás de Cloudflare + Access (email del equipo). Complementa Basic Auth.

---

## 5. Datos de pruebas (JSON)

Al arrancar, si `out/` está vacío, el entrypoint copia `deploy/railway-seed/*.json` y regenera la vitrina.

Actualizar métricas tras nuevas pruebas locales:

```powershell
$env:MMI_DEPLOY_MODE = "vitrina"
.venv\Scripts\python -m mmi.tools.vitrina
Copy-Item out\query-smoke.json,out\golden-set-eval.json,out\rag-validation.json,out\load-test-report.json,out\analysis-status.json,out\ingestion-results.json deploy\railway-seed\ -Force
git add deploy/railway-seed
git commit -m "Update vitrina seed stats"
git push
```

Railway redeploya y el seed queda en la imagen.

**Volumen opcional:** Settings → Volumes → montar `/app/out` para persistir JSON sin rebuild (luego subir archivos con Railway CLI o un job).

---

## 6. Comprobar

```bash
curl -s https://TU-SERVICIO.up.railway.app/api/motor/health
curl -s -o /dev/null -w "%{http_code}" https://TU-SERVICIO.up.railway.app/
curl -s -o /dev/null -w "%{http_code}" https://TU-SERVICIO.up.railway.app/search.html
curl -s -o /dev/null -w "%{http_code}" https://TU-SERVICIO.up.railway.app/rag.html
```

En el navegador: Inicio · Pruebas · Ejemplos · Búsqueda · Consulta RAG.

---

## 7. Coste y sizing

| | Orientativo |
|--|-------------|
| Plan Hobby / Trial | Suficiente para demo interna |
| RAM | 512 MB–1 GB (API + HTML) |
| Sleep | En Hobby el servicio puede dormir; Pro evita cold starts en demos |

Qdrant Cloud + Supabase + OpenRouter siguen siendo servicios externos (mismas keys que local).

---

## 8. Checklist

- [ ] Push rama con `deploy/Dockerfile`, `railway.toml`, `entrypoint.sh`
- [ ] Variables Qdrant / Supabase / OpenAI / OpenRouter
- [ ] `MMI_DEPLOY_MODE=vitrina`
- [ ] Domain `mmi.monitoring.lat` + CNAME Hostinger
- [ ] Health `/api/motor/health` OK
- [ ] Búsqueda y RAG responden
- [ ] Auth (Cloudflare Access u otra)
- [ ] Seed JSON al día en `deploy/railway-seed/`

---

## 9. Troubleshooting

| Síntoma | Acción |
|---------|--------|
| Build falla en `pip install` | Ver logs; falta `build-essential` (ya en Dockerfile) |
| 502 / health fail | Revisar vars Qdrant; logs del deploy |
| HTML sin métricas | Falta seed JSON → copiar a `deploy/railway-seed/` y redeploy |
| Logos rotos | Asegurar `public/monitoring-logo-horizontal.svg` en el repo |
| Consultas vacías | Keys de producción ≠ local o colección distinta |

CLI útil: `railway logs` · `railway up` (con [Railway CLI](https://docs.railway.com/guides/cli)).
