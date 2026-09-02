#!/bin/sh
set -eu

# Docker: WORKDIR=/app · Railpack/local: raíz del repo
if [ -d /app/src ]; then
  APP_ROOT=/app
  cd /app
elif [ -d ./src ]; then
  APP_ROOT="$(pwd)"
else
  echo "MMI: no se encuentra src/ (APP_ROOT)" >&2
  exit 1
fi

PORT="${PORT:-8773}"
if [ -n "${RAILWAY_ENVIRONMENT:-}" ]; then
  export MMI_DEPLOY_MODE=vitrina
  # Demo abierta por defecto: sin login. Cerrar con MMI_VITRINA_OPEN=0 + Basic Auth.
  export MMI_VITRINA_OPEN="${MMI_VITRINA_OPEN:-1}"
  export MMI_VITRINA_LIVE_QUERIES="${MMI_VITRINA_LIVE_QUERIES:-1}"
  if [ "$MMI_VITRINA_OPEN" = "1" ] || [ "$MMI_VITRINA_OPEN" = "true" ]; then
    unset MMI_BASIC_AUTH_USER || true
    unset MMI_BASIC_AUTH_PASSWORD || true
  fi
else
  export MMI_DEPLOY_MODE="${MMI_DEPLOY_MODE:-vitrina}"
fi
export MMI_BIND_HOST="${MMI_BIND_HOST:-0.0.0.0}"

mkdir -p "$APP_ROOT/out" "$APP_ROOT/public"

# Seed de JSON de pruebas (si el volumen out/ está vacío)
if [ -d "$APP_ROOT/deploy/railway-seed" ]; then
  for f in "$APP_ROOT/deploy/railway-seed"/*.json; do
    [ -f "$f" ] || continue
    base=$(basename "$f")
    if [ ! -f "$APP_ROOT/out/$base" ]; then
      cp "$f" "$APP_ROOT/out/$base"
      echo "seed -> out/$base"
    fi
  done
fi

echo "MMI Railway · root=$APP_ROOT · mode=$MMI_DEPLOY_MODE · live_queries=${MMI_VITRINA_LIVE_QUERIES:-unset} · open=${MMI_VITRINA_OPEN:-unset} · port=$PORT"
if [ -n "${MMI_BASIC_AUTH_USER:-}" ] && [ -n "${MMI_BASIC_AUTH_PASSWORD:-}" ]; then
  echo "MMI Railway · Basic Auth ON (user=${MMI_BASIC_AUTH_USER})"
else
  echo "MMI Railway · Basic Auth OFF (vitrina abierta)"
fi

# Regenerar HTML siempre (evita out/ viejo en volumen / caché de imagen)
echo "MMI Railway · regenerating vitrina HTML"
MMI_DEPLOY_MODE=vitrina python -m mmi.tools.vitrina

exec python -m mmi.tools.serve_local --host "$MMI_BIND_HOST" --port "$PORT" --no-replace
