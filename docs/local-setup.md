# ID Generator Service — Local Setup Guide

**Date**: 2026-03-28

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (running locally or via Docker)
- pip

---

## 1. Set Up PostgreSQL

### Option A: Docker (recommended)

```bash
docker run -d \
  --name idgen-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=idgenerator \
  -p 5432:5432 \
  postgres:16
```

To verify the container is running:

```bash
docker ps | grep idgen-postgres
```

To connect via `psql` (note: `-h localhost` is **required** on macOS because
`psql` defaults to Unix socket which Docker doesn't expose):

```bash
psql -h localhost -p 5432 -U postgres -d idgenerator
```

### Option B: Local PostgreSQL

If PostgreSQL is already running locally, create the database:

```bash
psql -h localhost -U postgres -c "CREATE DATABASE idgenerator;"
```

---

## 2. Clone and Install

```bash
cd /path/to/id-generator

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the service and its dependencies
pip install -e .

# (Optional) Install test dependencies too
pip install -r requirements-test.txt
```

---

## 3. Configure

### Database Connection (environment variables)

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=idgenerator
export DB_USER=postgres
export DB_PASSWORD=postgres
```

### Application Config

The default configuration is in `config/default.yaml`. It includes three
test namespaces (`test_ns_1`, `test_ns_2`, `test_perf_ns`).

To override any setting, either:
- Edit `config/default.yaml` directly, or
- Use environment variables with `__` as the nested delimiter:
  ```bash
  export ID_GENERATOR__POOL_MIN_THRESHOLD=500
  ```

To use a different config file:
```bash
export CONFIG_PATH=/path/to/my-config.yaml
```

### Changing Namespaces

You can rename, add, or remove namespaces in the config at any time:

- **Old namespace tables stay in the database** — no data is deleted. The
  service simply stops serving requests for namespaces not in the config
  (returns `IDG-003 Unknown namespace`).
- **New namespaces** get their tables created and pools filled on the next
  startup.
- **Re-adding an old namespace** to the config will pick up its existing
  table with all previously generated and issued IDs intact.
- **To permanently delete** an old namespace's data, a DBA must manually
  drop the table:
  ```bash
  psql -h localhost -U postgres -d idgenerator -c "DROP TABLE IF EXISTS id_pool_old_namespace;"
  ```

---

## 4. Run the Service

```bash
# From the project root directory (where config/ is located)
cd /path/to/id-generator

uvicorn id_generator.main:app --host 0.0.0.0 --port 8000 --reload
```

**First startup** will:
1. Connect to PostgreSQL
2. Create tables for each configured namespace (`id_pool_test_ns_1`, etc.)
3. Generate and insert IDs until each namespace has at least `pool_min_threshold` IDs
4. Start accepting HTTP requests

You should see logs like:
```
INFO  id_generator.main: Initializing database engine...
INFO  id_generator.main: Setting up namespace 'farmer_id' (id_length=5)...
INFO  id_generator.pool.manager: Namespace 'farmer_id': 0 AVAILABLE IDs (threshold: 1000)
INFO  id_generator.pool.manager: Namespace 'farmer_id': generated 1000, inserted 1000 (...)
INFO  id_generator.pool.manager: Namespace 'farmer_id': pool ready with 1000 AVAILABLE IDs
...
INFO  id_generator.main: Startup complete. All namespace pools are ready.
INFO  id_generator.main: Background pool replenishment started (interval: 30s)
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 5. Verify

### Interactive API docs

Open http://localhost:8000/docs in your browser for the Swagger UI.

### Quick test with curl

```bash
# Health check
curl http://localhost:8000/v1/idgenerator/health

# Version
curl http://localhost:8000/v1/idgenerator/version

# View configured namespaces
curl http://localhost:8000/v1/idgenerator/config

# Issue an ID (replace farmer_id with your namespace name)
curl -X POST http://localhost:8000/v1/idgenerator/farmer_id/id

# Validate an ID (replace farmer_id and 57382 with actual values)
curl http://localhost:8000/v1/idgenerator/farmer_id/id/validate/57382
```

---

## 6. Run Tests

Tests **auto-discover** namespace names and ID lengths from the running service
via `GET /v1/idgenerator/config`. No namespace names need to be specified.

With the service running locally:

```bash
cd tests

# Run all tests
pytest --base-url=http://localhost:8000 --html=report.html --self-contained-html -v

# Run against a remote service
pytest --base-url=https://idgen.staging.example.com -v

# Run only API contract tests (fast)
pytest -m api_contract --base-url=http://localhost:8000 -v

# Run only filter tests (fast, no IDs consumed)
pytest -m filters --base-url=http://localhost:8000 -v

# Run exhaustive tests (slow, consumes all IDs in small namespaces)
pytest -m exhaustive --base-url=http://localhost:8000 -v
```

**Important**: After running exhaustive tests, the two smallest-ID-length
namespaces are fully consumed. To re-run them, drop their tables and restart:

```bash
# Connect to PostgreSQL and drop the exhausted tables
# (replace farmer_id / household_id with your actual namespace names)
psql -h localhost -U postgres -d idgenerator -c "DROP TABLE IF EXISTS id_pool_farmer_id;"
psql -h localhost -U postgres -d idgenerator -c "DROP TABLE IF EXISTS id_pool_household_id;"

# Restart the service (tables will be re-created and pools re-filled)
```

---

## 7. Project Structure

```
id-generator/
├── config/
│   └── default.yaml             # Default configuration
├── docs/
│   ├── functional-specs.md
│   ├── technical-architecture.md
│   ├── test-plan.md
│   └── local-setup.md           # This file
├── src/
│   └── id_generator/
│       ├── main.py              # FastAPI app entry point
│       ├── config.py            # Settings (YAML + env vars)
│       ├── db.py                # Async SQLAlchemy engine
│       ├── models.py            # Table creation (table-per-namespace)
│       ├── api/
│       │   ├── router.py        # API endpoints
│       │   └── schema.py        # MOSIP response envelope
│       ├── generator/
│       │   ├── engine.py        # ID generation pipeline
│       │   ├── filters.py       # 10 filter implementations
│       │   └── verhoeff.py      # Verhoeff checksum
│       └── pool/
│           ├── manager.py       # Background replenishment
│           └── issuer.py        # Issue & mark TAKEN
├── tests/                       # Integration test suite
├── pyproject.toml
└── requirements-test.txt
```

---

## 8. Environment Variables Reference

### Required (Database)

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `idgenerator` | Database name (must exist) |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `postgres` | Database password |

### Optional (Application)

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFIG_PATH` | `config/default.yaml` | Path to YAML config file |
| `BUILD_TIME` | `dev` | Build timestamp (set in CI/CD) |
| `GIT_COMMIT` | `dev` | Git commit hash (set in CI/CD) |

### Optional (Config Overrides)

Any config value can be overridden via environment variables using `__` as
the nested delimiter:

```bash
export ID_GENERATOR__POOL_MIN_THRESHOLD=500
export ID_GENERATOR__SEQUENCE_LIMIT=4
export ID_GENERATOR__NAMESPACES__SOCIAL_ID__ID_LENGTH=10
```

---

## 9. Troubleshooting

### "Config file not found"
Make sure you run `uvicorn` from the project root directory (where `config/`
exists), or set `CONFIG_PATH` to the absolute path of your config file.

### "Database engine not initialized"
Check that PostgreSQL is running and the `DB_*` environment variables are set
correctly.

### Startup takes too long
For namespaces with large ID lengths (e.g., 10+ digits) and high
`pool_min_threshold`, the initial pool generation can take time. Reduce
`pool_min_threshold` for faster development iteration.

### "ID space exhausted" immediately
For short ID lengths (e.g., 5 digits), the valid ID space is small (~500-5000).
If `pool_min_threshold` is set too high, the space may exhaust on startup.
The service will log a warning and continue.
