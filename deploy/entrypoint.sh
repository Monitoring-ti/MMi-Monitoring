#!/bin/sh
set -eu

PORT="${PORT:-8773}"
if [ -n "${RAILWAY_ENVIRONMENT:-}" ]; then
  export MMI_DEPLOY_MODE=vitrina
  # Demo vitrina: Basic Auth + consultas al corpus (sobreescribible en Variables)
  export MMI_BASIC_AUTH_USER="${MMI_BASIC_AUTH_USER:-Pruena Monitoring}"
  export MMI_BASIC_AUTH_PASSWORD="${MMI_BASIC_AUTH_PASSWORD:-202608v1}"
  export MMI_VITRINA_LIVE_QUERIES="${MMI_VITRINA_LIVE_QUERIES:-1}"
else
  export MMI_DEPLOY_MODE="${MMI_DEPLOY_MODE:-vitrina}"
fi
export MMI_BIND_HOST="${MMI_BIND_HOST:-0.0.0.0}"

mkdir -p /app/out /app/public

# Seed de JSON de pruebas (si el volumen out/ está vacío)
if [ -d /app/deploy/railway-seed ]; then
  for f in /app/deploy/railway-seed/*.json; do
    [ -f "$f" ] || continue
    base=$(basename "$f")
    if [ ! -f "/app/out/$base" ]; then
      cp "$f" "/app/out/$base"
      echo "seed -> out/$base"
    fi
  done
fi

echo "MMI Railway · mode=$MMI_DEPLOY_MODE · live_queries=${MMI_VITRINA_LIVE_QUERIES:-unset} · port=$PORT"
if [ -n "${MMI_BASIC_AUTH_USER:-}" ] && [ -n "${MMI_BASIC_AUTH_PASSWORD:-}" ]; then
  echo "MMI Railway · Basic Auth ON (user=${MMI_BASIC_AUTH_USER})"
else
  echo "MMI Railway · Basic Auth OFF (definir MMI_BASIC_AUTH_USER/PASSWORD)"
fi
exec python -m mmi.tools.serve_local --host "$MMI_BIND_HOST" --port "$PORT" --no-replace
