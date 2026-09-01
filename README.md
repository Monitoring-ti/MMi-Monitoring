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

## Web app (Next.js)

```bash
npm install
npm run dev
```

## Git

Repo: `git@github.com:Monitoring-ti/MMi-Monitoring.git`
