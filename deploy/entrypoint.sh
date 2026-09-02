#!/bin/sh
set -eu

PORT="${PORT:-8773}"
export MMI_DEPLOY_MODE="${MMI_DEPLOY_MODE:-vitrina}"
export MMI_BIND_HOST="${MMI_BIND_HOST:-0.0.0.0}"

mkdir -p /app/out /app/public

# Seed de JSON de pruebas (si el volumen out/ está vacío)
if [ -d /app/deploy/railway-seed ]; then
  for f in /app/deploy/railway-seed/*; do
    [ -f "$f" ] || continue
    base=$(basename "$f")
    if [ ! -f "/app/out/$base" ]; then
      cp "$f" "/app/out/$base"
      echo "seed -> out/$base"
    fi
  done
fi

echo "MMI Railway · mode=$MMI_DEPLOY_MODE · port=$PORT"
exec python -m mmi.tools.serve_local --host "$MMI_BIND_HOST" --port "$PORT" --no-replace
