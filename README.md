# MMI by Monitoring

Monorepo del producto **Monitoring Maintenance Intelligence** para el sector minero: memoria técnica industrial con RAG documental, citas verificables y capa web comercial.

## Componentes

| Ruta | Rol |
|------|-----|
| `src/mmi/` | Pipeline Python — ingesta, indexación, búsqueda híbrida, RAG, Motor MMI, Mapa |
| `docs/` | Planes operativos y especificaciones |
| `fixtures/` | Datos de prueba (no corpus cliente) |
| `app/` | Aplicación web Next.js (presentación comercial / demo) |
| `public/` | Assets estáticos web |

## Backend Python (RAG)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Copiar `.env.example` → `.env` (no commitear secretos).

```powershell
.venv\Scripts\python -m mmi.tools.serve_local --port 8773
```

UI: `search.html` · `rag.html` · `mapa.html` · `motor.html` · `review.html`

Plan operativo: [`docs/plan.md`](docs/plan.md) · comandos: [`docs/plan-anexo-operaciones.md`](docs/plan-anexo-operaciones.md)

## Vitrina (deploy público)

Modo **solo pruebas + consultas** — sin ingesta ni portal dev.

```powershell
$env:MMI_DEPLOY_MODE = "vitrina"
.venv\Scripts\python -m mmi.tools.vitrina
.venv\Scripts\python -m mmi.tools.serve_local --port 8773
```

Páginas: `/` · `/pruebas.html` · `/ejemplos.html` · `/search.html` · `/rag.html`

**Deploy:** [Railway](deploy/RAILWAY.md) (camino principal) · [Vitrina overview](deploy/VITRINA.md) · [VPS + n8n](deploy/VPS-N8N.md)


```bash
npm install
npm run dev
# → http://localhost:3000 — demo operativa en #demo
```

Requiere el backend en `:8773` (proxy automático vía `next.config.ts`).  
Integración: [`docs/plan-integracion-ui.md`](docs/plan-integracion-ui.md)

## Git

Repo: `git@github.com:Monitoring-ti/MMi-Monitoring.git`
