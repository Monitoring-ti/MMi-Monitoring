FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
EXPOSE 8773

# Generación de HTML al arrancar (stats + portal)
CMD ["python", "-m", "mmi.tools.serve_local", "--port", "8773", "--host", "0.0.0.0", "--no-replace"]
