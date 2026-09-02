FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY public ./public
COPY deploy/entrypoint.sh ./deploy/entrypoint.sh
COPY deploy/railway-seed ./deploy/railway-seed

RUN pip install --no-cache-dir -e . \
    && chmod +x /app/deploy/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV MMI_DEPLOY_MODE=vitrina
ENV MMI_BIND_HOST=0.0.0.0
EXPOSE 8773

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:'+__import__('os').environ.get('PORT','8773')+'/api/motor/health')" || exit 1

ENTRYPOINT ["/app/deploy/entrypoint.sh"]
