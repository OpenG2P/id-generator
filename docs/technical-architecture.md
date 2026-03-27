# ID Generator Service — Technical Architecture

**Version**: 0.1
**Date**: 2026-03-27
**Status**: Draft

---

## 1. Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python | Team standard |
| Web Framework | FastAPI (async) | As specified; async-native maps well to I/O-bound workload |
| DB Driver | `asyncpg` | Native async PostgreSQL driver, best performance |
| ORM | SQLAlchemy 2.x (async) | Mature async support, Alembic for migrations |
| Migrations | Alembic | Standard for SQLAlchemy; manages schema structure |
| Config | Pydantic Settings | Loads from YAML with environment variable overrides |
| Randomness | Python `secrets` module | Cryptographically secure; no periodic re-seeding needed |
| Database | PostgreSQL | As specified |
| Deployment | Kubernetes | Horizontal pod scaling |

Full async top-to-bottom — no thread pool hacks. FastAPI's async nature maps well to the I/O-bound workload (DB reads/writes).

---

## 2. Project Structure

```
id-generator/
├── pyproject.toml
├── Dockerfile
├── alembic/                     # DB migrations (schema structure only)
│   └── versions/
├── config/
│   └── default.yaml             # Default config (namespaces, filter params)
├── src/
│   └── id_generator/
│       ├── main.py              # FastAPI app entry point
│       ├── config.py            # Pydantic Settings (YAML + env vars)
│       ├── db.py                # Async SQLAlchemy engine, session
│       ├── models.py            # SQLAlchemy ORM model (id_pool table factory)
│       ├── api/
│       │   ├── router.py        # FastAPI routes
│       │   └── schema.py        # Pydantic request/response models (MOSIP envelope)
│       ├── generator/
│       │   ├── engine.py        # Core ID generation (random + checksum)
│       │   ├── filters.py       # All 10 filter implementations
│       │   └── verhoeff.py      # Verhoeff checksum algorithm
│       └── pool/
│           ├── manager.py       # Pool replenishment logic
│           └── issuer.py        # Fetch & mark TAKEN logic
└── tests/
```

**Design principle**: Separate `generator` (pure functions, no DB dependency) from `pool` (DB-dependent). Filters and Verhoeff are independently testable.

---

## 3. Database Design

### 3.1 Table-Per-Namespace Strategy

Each namespace gets its own table, auto-created on startup. No `namespace` column — the table name is the namespace.

```sql
-- Auto-created for each namespace on startup
CREATE TABLE IF NOT EXISTS id_pool_{namespace} (
    id_value        VARCHAR(32)     PRIMARY KEY,
    status          VARCHAR(16)     NOT NULL DEFAULT 'AVAILABLE',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    issued_at       TIMESTAMPTZ     NULL
);

CREATE INDEX IF NOT EXISTS idx_{namespace}_available
    ON id_pool_{namespace} (status) WHERE status = 'AVAILABLE';
```

### 3.2 Why Table-Per-Namespace (Not Single Table)

| Aspect | Single Table | Table-Per-Namespace (chosen) |
|--------|--------------|------------------------------|
| Query performance | All namespaces share one B-tree index. At 50M x N rows, index grows large. | Each table has its own smaller index. 50M rows per table is a PostgreSQL sweet spot. |
| Bulk insert | Inserting into a 200M+ row table — heavier index maintenance. | Inserting into a 50M row table — lighter index updates. |
| VACUUM / maintenance | One large table to vacuum. Bloat accumulates across all namespaces. | Smaller tables vacuum faster. Can schedule maintenance per namespace independently. |
| Dropping a namespace | `DELETE FROM id_pool WHERE namespace = :ns` — slow on 50M rows, generates WAL bloat. | `DROP TABLE id_pool_{ns}` — instant, clean. |
| Adding a namespace | Just add rows to existing table. | `CREATE TABLE IF NOT EXISTS` on startup. |
| Code complexity | Single model, namespace is a column. Simpler. | Dynamic table names at runtime. Slightly more complex but manageable via a table factory. |

### 3.3 Table Lifecycle

- **On startup**: For each namespace in config, run `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`. Existing tables are untouched.
- **On namespace removal**: Table is left in place (orphaned but safe). Manual `DROP TABLE` by DBA if cleanup is needed.
- **Namespace naming**: Validated against config (alphanumeric + underscore only) to prevent SQL injection in table names.

### 3.4 Schema Migrations

- **Alembic** manages the schema structure (what columns the tables have).
- **Table creation per namespace** is handled at app startup, not via Alembic migrations.

---

## 4. Issuing IDs — Concurrency-Safe Path

This is the most performance-sensitive and concurrency-critical part.

### 4.1 SQL Pattern

```sql
-- Atomic: select + lock in one step
SELECT id_value FROM id_pool_{namespace}
WHERE status = 'AVAILABLE'
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- Mark as taken
UPDATE id_pool_{namespace}
SET status = 'TAKEN', issued_at = now()
WHERE id_value = :id;
```

Both statements execute in a single transaction.

### 4.2 Why `FOR UPDATE SKIP LOCKED`

- With plain `FOR UPDATE`: if Pod A locks a row, Pod B **waits** (blocks).
- With `FOR UPDATE SKIP LOCKED`: Pod B **skips** the locked row and grabs the next available one.
- Result: **zero contention** between pods — every pod gets an instant response regardless of concurrent load.
- This is the standard PostgreSQL pattern for job queues and pool dispensers.

---

## 5. Pool Replenishment

### 5.1 Background Task

Every pod runs a periodic background task (every 30 seconds, configurable via `pool_check_interval_seconds`):

```
For each namespace in config:
    1. COUNT(*) FROM id_pool_{namespace} WHERE status = 'AVAILABLE'
    2. If count < pool_min_threshold:
         Try: pg_try_advisory_lock(hash(namespace))
         If lock acquired:
             Generate IDs in sub-batches (e.g., 10K per transaction)
             Insert into id_pool_{namespace}
             Release advisory lock
         If lock NOT acquired:
             Skip — another pod is already generating for this namespace
```

### 5.2 Why PostgreSQL Advisory Locks

- **No leader election needed** — any pod can generate, but only one at a time per namespace.
- **`pg_try_advisory_lock`** is non-blocking — if another pod holds the lock, we skip instantly (no waiting).
- **Database is the coordinator** — no need for Redis, ZooKeeper, or K8s leader election.
- **Per-namespace locks** — Pod A can generate for `social_id` while Pod B generates for `farmer_id` simultaneously.

### 5.3 Alternatives Considered and Rejected

| Alternative | Why rejected |
|-------------|--------------|
| Let all pods generate, rely on unique constraint | Wasteful. ID generation is CPU-intensive (filters reject many candidates). Duplicated work is thrown away. |
| Separate worker pod for generation | Adds operational complexity (another deployment, scaling rules). Not justified at this scale. |

### 5.4 Sub-Batch Insertion

IDs are generated and inserted in smaller sub-batches (e.g., 10K per transaction) rather than one large batch:
- Avoids long-running transactions that hold locks.
- Reduces WAL pressure.
- Allows other operations (like issuing) to interleave without being blocked.

---

## 6. ID Generation Pipeline

```
┌─────────────────────────────────────────────────────┐
│  For each ID in batch:                               │
│                                                      │
│  1. secrets.randbelow(upper_bound)                   │
│       → raw (length-1) digit string, zero-padded     │
│                                                      │
│  2. Verhoeff checksum → append 1 digit               │
│       → candidate ID                                 │
│                                                      │
│  3. Run 10 filters (ordered cheapest-first):         │
│       a. not_start_with         (string prefix)      │
│       b. length                 (string length)      │
│       c. sequence               (regex/scan)         │
│       d. repeating_digit        (regex)              │
│       e. repeating_block        (regex)              │
│       f. conjugative_even       (regex)              │
│       g. first_equals_last      (string slice)       │
│       h. first_equals_reverse   (string slice)       │
│       i. restricted_numbers     (substring search)   │
│       j. cyclic_numbers         (substring search)   │
│                                                      │
│  4. If all pass → collect for DB insert              │
│     If any fail → discard, generate next             │
│                                                      │
│  5. INSERT ... ON CONFLICT DO NOTHING                │
│       → silently skips duplicates                    │
└─────────────────────────────────────────────────────┘
```

### 6.1 Key Design Points

- **Filters run in-memory before DB insert** — cheap and fast. Only valid IDs hit the database.
- **`INSERT ... ON CONFLICT DO NOTHING`** — handles the rare case where a generated ID already exists (either AVAILABLE or TAKEN). No error, just skips.
- **Filter ordering**: Cheapest and most-likely-to-reject filters run first (e.g., `not_start_with` rejects ~20% of candidates immediately) to fail fast.
- **Pure functions**: The generator and filters have no database dependency. They can be unit tested in isolation.

---

## 7. ID Space Exhaustion Detection

### 7.1 Detection Strategy

- When issuing: if no AVAILABLE IDs exist, **trigger an immediate replenishment attempt** (don't wait for the periodic 30s task).
- If the replenishment attempt generates **zero valid IDs** after N random attempts (configurable via `exhaustion_max_attempts`, e.g., 1000), declare the space exhausted.
- This distinguishes between:
  - **`IDG-001`** (temporary): Pool is empty but space is not exhausted. Replenishment is running. Caller should retry.
  - **`IDG-002`** (permanent): Pool is empty AND generation failed after max attempts. Space is exhausted. No recovery possible.

---

## 8. Startup Behavior

On application startup:

```
1. Connect to PostgreSQL
2. For each namespace in config:
     a. CREATE TABLE IF NOT EXISTS id_pool_{namespace} (...)
     b. CREATE INDEX IF NOT EXISTS idx_{namespace}_available (...)
     c. COUNT AVAILABLE IDs
     d. If count < pool_min_threshold:
          Generate IDs until threshold is met (blocking)
3. Start FastAPI server (begin accepting requests)
```

**The service blocks until all namespaces have their minimum pool generated.** This ensures no `IDG-001` errors immediately after deployment.

Kubernetes implications:
- **Readiness probe** should point to the `/v1/idgenerator/health` endpoint, which only returns healthy after startup is complete.
- **Liveness probe** can be a simpler TCP check.
- Initial startup for a new namespace may take time depending on `pool_min_threshold` and ID length. K8s `initialDelaySeconds` should be set accordingly.

---

## 9. Configuration Management

### 9.1 Configuration File

```yaml
# config/default.yaml
id_generator:
  # Global filter rules
  sequence_limit: 3
  repeating_limit: 2
  repeating_block_limit: 2
  conjugative_even_digits_limit: 3
  digits_group_limit: 5
  reverse_digits_group_limit: 5
  not_start_with: ["0", "1"]
  restricted_numbers: []

  # Pool management
  pool_min_threshold: 100000        # Trigger generation below this count
  pool_generation_batch_size: 200000 # IDs per replenishment cycle
  pool_check_interval_seconds: 30    # How often to check pool levels
  exhaustion_max_attempts: 1000      # Random attempts before declaring exhaustion

  # Namespaces
  namespaces:
    social_id:
      id_length: 10
    farmer_id:
      id_length: 12
    health_id:
      id_length: 10
```

### 9.2 Environment Variable Overrides

Pydantic Settings supports environment variable overrides with nested prefix notation:

```bash
ID_GENERATOR__POOL_MIN_THRESHOLD=50000
ID_GENERATOR__NAMESPACES__SOCIAL_ID__ID_LENGTH=12
```

Environment variables take precedence over YAML values, enabling per-deployment customization without changing the config file.

---

## 10. Kubernetes Deployment Architecture

```
┌─────────────────────────────────────────────────────┐
│                Kubernetes Cluster                     │
│                                                       │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────┐│
│   │    Pod 1      │  │    Pod 2      │  │   Pod 3    ││
│   │   FastAPI     │  │   FastAPI     │  │  FastAPI   ││
│   │ + background  │  │ + background  │  │+ background││
│   │ pool manager  │  │ pool manager  │  │pool manager││
│   └──────┬───────┘  └──────┬───────┘  └─────┬──────┘│
│          │                  │                 │        │
│          └──────────┬───────┘─────────────────┘        │
│                     │                                  │
│             ┌───────▼────────┐                         │
│             │  PostgreSQL    │                         │
│             │  (single DB)   │                         │
│             └────────────────┘                         │
└─────────────────────────────────────────────────────┘
```

### 10.1 Pod Design

- **Every pod is identical** — runs both the FastAPI server and the background pool manager.
- **No leader pod** — PostgreSQL advisory locks coordinate generation naturally.
- **Horizontal scaling**: Add pods for more API throughput.

### 10.2 Connection Pooling

- SQLAlchemy async connection pool per pod (e.g., 10 connections per pod).
- For many pods (10+), consider deploying **PgBouncer** in front of PostgreSQL to avoid exceeding PostgreSQL's `max_connections`.

### 10.3 Probes

| Probe | Endpoint / Check | Purpose |
|-------|------------------|---------|
| Readiness | `GET /v1/idgenerator/health` | Only healthy after startup pool generation is complete |
| Liveness | TCP check on port | Detect crashed processes |

---

## 11. Key Architectural Decisions Summary

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Async stack | Full async (FastAPI + asyncpg + SQLAlchemy async) | I/O-bound workload, no thread pool overhead |
| 2 | Table strategy | Table-per-namespace, auto-created on startup | Clean isolation, better vacuum/maintenance, instant DROP |
| 3 | Issuing concurrency | `SELECT ... FOR UPDATE SKIP LOCKED` | Zero contention between pods |
| 4 | Generation coordination | PostgreSQL advisory locks (`pg_try_advisory_lock`) | No external coordinator needed, per-namespace parallelism |
| 5 | Bulk insert | Sub-batches (e.g., 10K per transaction) | Avoids long transactions, reduces WAL pressure |
| 6 | Duplicate handling | `INSERT ... ON CONFLICT DO NOTHING` | Silently skips, no error handling needed |
| 7 | Filter execution | In-memory, ordered cheapest-first, before DB insert | Fail fast, no wasted DB writes |
| 8 | Startup behavior | Block until minimum pool is generated | No IDG-001 errors immediately after deployment |
| 9 | Health / readiness | DB ping only; readiness tied to startup completion | Simple, sufficient |
| 10 | Config management | Pydantic Settings: YAML + env var overrides | Flexible for K8s (ConfigMap + env vars) |
