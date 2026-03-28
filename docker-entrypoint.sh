#!/bin/sh
# Entrypoint script for ID Generator Service
# Uses exec so uvicorn receives signals (SIGTERM) directly from Docker

exec uvicorn id_generator.main:app \
    --host "${UVICORN_HOST:-0.0.0.0}" \
    --port "${UVICORN_PORT:-8000}" \
    --workers "${UVICORN_WORKERS:-1}" \
    --log-level "${UVICORN_LOG_LEVEL:-info}" \
    --loop asyncio
