# =============================================================================
# ID Generator Service — Multi-stage Docker Build
# =============================================================================
# Build:
#   docker build -t id-generator:latest \
#     --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) \
#     --build-arg BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ") .
#
# Run:
#   docker run -p 8000:8000 \
#     -e DB_HOST=host.docker.internal \
#     -e DB_PORT=5432 \
#     -e DB_NAME=idgenerator \
#     -e DB_USER=postgres \
#     -e DB_PASSWORD=postgres \
#     id-generator:latest
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS builder

WORKDIR /build

# Install build dependencies
COPY pyproject.toml .
COPY src/ src/
COPY config/ config/

# Build wheel
RUN pip install --no-cache-dir build && \
    python -m build --wheel --outdir /build/dist

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:3.13-slim

# Build-time arguments (baked into image)
ARG GIT_COMMIT=dev
ARG BUILD_TIME=dev

# Bake build metadata into env vars
ENV GIT_COMMIT=${GIT_COMMIT}
ENV BUILD_TIME=${BUILD_TIME}

# Database connection (must be provided at runtime)
ENV DB_HOST=localhost
ENV DB_PORT=5432
ENV DB_NAME=idgenerator
ENV DB_USER=postgres
ENV DB_PASSWORD=postgres

# Application config (can be overridden at runtime)
ENV CONFIG_PATH=/app/config/default.yaml

# Uvicorn settings
ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=8000
ENV UVICORN_WORKERS=1
ENV UVICORN_LOG_LEVEL=info

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home appuser

WORKDIR /app

# Install the wheel from build stage
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm -f /tmp/*.whl

# Copy config
COPY --chown=appuser:appuser config/ /app/config/

# Switch to non-root user
USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/idgenerator/health')" || exit 1

# Start the service
CMD uvicorn id_generator.main:app \
    --host ${UVICORN_HOST} \
    --port ${UVICORN_PORT} \
    --workers ${UVICORN_WORKERS} \
    --log-level ${UVICORN_LOG_LEVEL} \
    --loop asyncio
