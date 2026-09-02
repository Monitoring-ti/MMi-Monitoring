# VPS Hostinger — MMI + n8n en el mismo servidor

Guía para desplegar **mmi.monitoring.lat** sin tocar el stack de **n8n** que ya viene en la plantilla Ubuntu 24.04.

**VPS de referencia:** `srv1748637.hstgr.cloud` · `2.25.197.231` · 4 vCPU · 16 GB RAM

---

## 1. Regla de oro: no tocar n8n

| ✅ Hacer | ❌ No hacer |
|----------|-------------|
| Añadir **nuevo** sitio nginx `mmi.monitoring.lat` | Modificar el `docker-compose` de n8n |
| Instalar MMI en `/opt/mmi` | Cambiar puertos del contenedor n8n |
| Exponer MMI solo vía nginx `:443` | Liberar/detener contenedores n8n |
| API MMI en `127.0.0.1:8773` (solo localhost) | Publicar `:8773` ni `:5678` en el firewall |

n8n sigue en su contenedor Docker habitual (puerto interno **5678**). MMI es un servicio **aparte**.

---

## 2. Mapa de puertos (objetivo)

```
Internet
   │
   ▼
:443  nginx (host) ── TLS
   │
   ├── server_name n8n.tu-dominio...  →  127.0.0.1:5678  (n8n, ya existente)
   │
   └── server_name mmi.monitoring.lat →  estáticos /opt/mmi/out
                                        + /api/* → 127.0.0.1:8773 (MMI)

:22   SSH (restringir IP si podéis)

CERRADOS al exterior: 8773, 5678, 8773
```

---

## 3. Antes de empezar — inventario

Conectad por SSH y anotad cómo está n8n hoy:

```bash
ssh root@2.25.197.231

# Contenedores
docker ps

# Puertos en escucha
ss -tlnp | grep -E '443|80|5678|8773'

# ¿nginx ya instalado?
nginx -v 2>/dev/null || echo "sin nginx"
ls /etc/nginx/sites-enabled/ 2>/dev/null
```

Anotad:
- Nombre del contenedor n8n
- Si n8n usa dominio propio (ej. `n8n.monitoring.lat`) o solo IP:5678
- Si Hostinger ya configuró nginx/Traefik delante de n8n

**No cambiéis nada** en este paso; solo observad.

---

## 4. DNS (Hostinger)

| Tipo | Nombre | Valor |
|------|--------|-------|
| **A** | `mmi` | `2.25.197.231` |

n8n mantiene su registro DNS actual (otro subdominio o el mismo VPS con otro `server_name`).

---

## 5. Instalar MMI en `/opt/mmi`

```bash
apt update && apt install -y git python3.12-venv nginx certbot python3-certbot-nginx apache2-utils

mkdir -p /opt/mmi && cd /opt/mmi

# Clonar (deploy key o HTTPS)
git clone git@github.com:Monitoring-ti/MMi-Monitoring.git .
git checkout feature/mmi-operational-web   # o main cuando mergeéis

python3 -m venv .venv
.venv/bin/pip install -e .

# Secretos — copiar desde máquina local, nunca al repo
nano /opt/mmi/.env
```

`.env` mínimo en producción:

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

Carpeta de stats (sync desde local):

```bash
mkdir -p /opt/mmi/out
# Tras cada lote local, scp de JSON (ver sección 9)
```

Generar páginas vitrina:

```bash
cd /opt/mmi
export MMI_DEPLOY_MODE=vitrina
.venv/bin/python -m mmi.tools.vitrina
.venv/bin/python -m mmi.tools.serve_local --port 8773 --no-replace &
# probar:
curl -s http://127.0.0.1:8773/api/motor/health
kill %1
```

Ver guía completa: [`deploy/VITRINA.md`](VITRINA.md)

---

## 6. Servicio systemd (MMI API)

Archivo `/etc/systemd/system/mmi-api.service`:

```ini
[Unit]
Description=MMI operational API (serve_local)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mmi
EnvironmentFile=/opt/mmi/.env
# MMI_DEPLOY_MODE=vitrina  (preferible fijarlo en .env)
ExecStart=/opt/mmi/.venv/bin/python -m mmi.tools.serve_local --port 8773 --no-replace
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable mmi-api
systemctl start mmi-api
systemctl status mmi-api
curl http://127.0.0.1:8773/api/motor/health
```

`serve_local` escucha en **127.0.0.1:8773** — no accesible desde fuera del VPS.

---

## 7. nginx — sitio nuevo para MMI

Creá un archivo **nuevo**, sin editar la config de n8n:

`/etc/nginx/sites-available/mmi.monitoring.lat`

```nginx
# Usuarios para Basic Auth (equipo + cliente)
# htpasswd -c /etc/nginx/.htpasswd-mmi monitoring

server {
    listen 80;
    server_name mmi.monitoring.lat;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name mmi.monitoring.lat;

    ssl_certificate     /etc/letsencrypt/live/mmi.monitoring.lat/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mmi.monitoring.lat/privkey.pem;

    # No indexar
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;

    auth_basic "MMI Monitoring";
    auth_basic_user_file /etc/nginx/.htpasswd-mmi;

    root /opt/mmi/out;
    index index.html;

    location = /robots.txt {
        auth_basic off;
        return 200 "User-agent: *\nDisallow: /\n";
        add_header Content-Type text/plain;
    }

    # API → Python (solo localhost)
    location /api/ {
        proxy_pass http://127.0.0.1:8773;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # JSON de stats (lectura)
    location ~* \.(json)$ {
        add_header Cache-Control "no-store";
        try_files $uri =404;
    }

    location / {
        try_files $uri $uri/ =404;
        add_header Cache-Control "no-store";
    }
}
```

Activar:

```bash
htpasswd -c /etc/nginx/.htpasswd-mmi admin
# certificado (nginx debe poder validar dominio)
certbot certonly --nginx -d mmi.monitoring.lat

ln -sf /etc/nginx/sites-available/mmi.monitoring.lat /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### Si n8n ya usa nginx en el mismo `:443`

Solo añadís **otro bloque `server`** (otro `server_name`). nginx enruta por dominio:

- `n8n.lo-que-sea` → proxy `:5678` (config existente, **intacta**)
- `mmi.monitoring.lat` → `/opt/mmi/out` + `/api/`

No hace falta un segundo nginx.

### Si n8n expone `:5678` directo al mundo

Opcional (recomendado): poner n8n detrás de nginx con subdominio y **cerrar 5678** en firewall. Eso es mejora de n8n, no requisito para MMI — MMI no usa ese puerto.

---

## 8. Firewall

```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw deny 5678/tcp
ufw deny 8773/tcp
ufw enable
ufw status
```

n8n sigue accesible por **HTTPS vía nginx** (si ya lo teníais) o por túnel SSH; el puerto 5678 no queda abierto al público.

---

## 9. Sync stats desde local (vitrina)

En la máquina de desarrollo, tras cerrar pruebas o un lote:

```powershell
cd mmi-by-monitoring
$env:MMI_DEPLOY_MODE = "vitrina"
.venv\Scripts\python -m mmi.tools.vitrina
.\scripts\publish_vitrina.ps1 -Host root@2.25.197.231
```

O manualmente:

```powershell
scp out/query-smoke.json out/golden-set-eval.json out/rag-validation.json `
    out/load-test-report.json out/analysis-status.json out/ingestion-results.json `
    root@2.25.197.231:/opt/mmi/out/

ssh root@2.25.197.231 "cd /opt/mmi && export MMI_DEPLOY_MODE=vitrina && .venv/bin/python -m mmi.tools.vitrina && systemctl restart mmi-api"
```

Solo JSON (sin HTML): `.\scripts\publish_vitrina.ps1 -JsonOnly`

**No reiniciáis n8n.** Detalle: [`VITRINA.md`](VITRINA.md)

---

## 10. Comprobaciones finales

```bash
# n8n sigue vivo
docker ps | grep n8n
curl -s -o /dev/null -w "%{http_code}" https://URL-DE-N8N-QUE-YA-USABais/

# MMI
curl -s -u admin:CLAVE https://mmi.monitoring.lat/api/motor/health
curl -s -u admin:CLAVE -o /dev/null -w "%{http_code}" https://mmi.monitoring.lat/
```

Desde navegador (con Basic Auth): `https://mmi.monitoring.lat/`

---

## 11. Recursos estimados

| Servicio | RAM |
|----------|-----|
| n8n (Docker) | ~0,5–1,5 GB |
| mmi-api (systemd) | ~0,5–2 GB |
| nginx | ~50 MB |
| **Total** | ~2–4 GB de 16 GB |

---

## 12. Resolución de problemas

| Síntoma | Causa probable | Acción |
|---------|----------------|--------|
| n8n dejó de responder | Se editó su compose/nginx | Restaurar backup; MMI no debe tocar esos archivos |
| 502 en `/api/` | `mmi-api` caído | `systemctl status mmi-api` · logs `journalctl -u mmi-api -f` |
| 404 en HTML | Falta sync `out/` | `scp` JSON + regenerar landing |
| Conflicto puerto 443 | Dos procesos escuchan | `ss -tlnp \| grep 443` — solo nginx |
| Consultas vacías | `.env` Qdrant/Supabase mal | Verificar keys en VPS vs local |

---

## 13. Alternativa: MMI en Docker (sin mezclar con n8n)

Si preferís contenedor para MMI, usad **red y compose separados**:

```bash
cd /opt/mmi/deploy
docker compose -f docker-compose.mmi.yml up -d
```

El compose de n8n **no se incluye** en ese archivo. Puerto publicado solo en localhost:

`127.0.0.1:8773:8773`

Ver `deploy/docker-compose.mmi.yml` en el repo.

---

## 14. Checklist

- [ ] Inventario `docker ps` / nginx n8n (sin cambios)
- [ ] DNS `mmi` → IP VPS
- [ ] `/opt/mmi` + `.env` + systemd `mmi-api`
- [ ] nginx sitio **nuevo** `mmi.monitoring.lat`
- [ ] certbot SSL
- [ ] htpasswd Basic Auth
- [ ] ufw: 443 sí, 5678/8773 no
- [ ] Sync JSON stats desde local
- [ ] Probar n8n + MMI en paralelo
