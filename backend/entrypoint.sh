#!/bin/sh
# entrypoint.sh — run DB migrations then start the API
# Used by: apps/api/Dockerfile CMD
set -e

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] Starting API on port ${APP_PORT:-8000}..."
exec uvicorn apps.api.main:app \
    --host 0.0.0.0 \
    --port "${APP_PORT:-8000}" \
    --workers "${UVICORN_WORKERS:-1}" \
    --log-level "${LOG_LEVEL:-info}"
