FROM python:3.11-slim AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# System deps (psycopg needs libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir ".[dev]"

COPY . /app/

# P3-01: entrypoint runs alembic migrate then uvicorn
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["/app/entrypoint.sh"]
