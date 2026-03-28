# ID Generator Service — Functional Specification

**Version**: 0.1
**Date**: 2026-03-27
**Status**: Draft

---

## 1. Overview

A FastAPI-based service that generates unique, random numeric IDs for multiple consuming applications (social ID, farmer ID, family ID, health ID, etc.). Each application operates within its own **namespace**, with an independent pool of pre-generated IDs. The service is designed to be horizontally scalable on Kubernetes.

**Reference**: Based on [MOSIP UIN Generator](https://docs.mosip.io/1.2.0/id-lifecycle-management/supporting-components/commons/id-generator#uin-generation-filters) with extensions for multi-namespace support.

---

## 2. Namespace / Realm

- Each consuming application is assigned a **namespace** (e.g., `social_id`, `farmer_id`, `health_id`).
- Namespaces are **pre-configured** (via config file / environment), not created via API.
- Each namespace has **one configurable parameter: ID length** (up to 32 digits).
- All ID generation/filter rules are **global** (same across all namespaces).
- The **same numeric ID may exist in multiple namespaces** — pools are fully independent.

### 2.1 Adding a Namespace

- Add the new namespace to the configuration file (YAML / Helm values).
- Perform a rolling restart of pods (e.g., `kubectl rollout restart` or Helm upgrade).
- On startup, the service auto-creates the database table for the new namespace (`CREATE TABLE IF NOT EXISTS`). Existing namespace tables are untouched — all previously generated and issued IDs are fully preserved.
- The service blocks until the minimum pool is generated for the new namespace, then begins serving requests.

### 2.2 Removing a Namespace

- Remove the namespace from the configuration file and restart pods.
- The service will no longer serve requests for the removed namespace — it returns `IDG-003 Unknown namespace`.
- The database table for the removed namespace is **not** automatically dropped. This is a safety measure — a configuration typo should not wipe millions of IDs.
- If storage reclaim is needed, a DBA can manually drop the orphaned table.

---

## 3. ID Generation Rules

### 3.1 Structure

- **Numeric only** — no alphabets or special characters.
- **Length**: Configurable per namespace, maximum 32 digits.
- **Last digit**: Verhoeff checksum — the generator produces `(length - 1)` random digits and appends 1 checksum digit.
- **Randomness**: Python `secrets` module (cryptographically secure). No periodic re-seeding needed.

### 3.2 Filters (All Must Pass)

Every generated ID must pass **all 10 filters**. Filter threshold parameters are globally configurable.

| # | Filter | Description | Config Key |
|---|--------|-------------|------------|
| 1 | **Length** | ID must be exactly the configured length for its namespace | Per-namespace `id_length` |
| 2 | **Not-Start-With** | ID must not begin with specified digits (e.g., 0, 1) | `not_start_with` (list) |
| 3 | **Sequence** | No ascending/descending consecutive sequences beyond limit (e.g., limit=3 → "123" rejected, "12" allowed) | `sequence_limit` |
| 4 | **Repeating Digit** | No same digit repeating within N positions (e.g., limit=2 → "11" and "1x1" rejected) | `repeating_limit` |
| 5 | **Repeating Block** | No repeated digit blocks (e.g., limit=2 → "48xx48" rejected) | `repeating_block_limit` |
| 6 | **Conjugative Even Digits** | No N consecutive even digits (2,4,6,8) in a row | `conjugative_even_digits_limit` |
| 7 | **First = Last** | First N digits must not equal last N digits | `digits_group_limit` |
| 8 | **First = Reverse(Last)** | First N digits must not equal reverse of last N digits | `reverse_digits_group_limit` |
| 9 | **Restricted Numbers** | ID must not contain any blacklisted substrings | `restricted_numbers` (list) |
| 10 | **Cyclic Numbers** | ID must not contain any of the 9 known mathematical cyclic number patterns | Hardcoded list |

### 3.3 Cyclic Numbers (Hardcoded)

The following cyclic number patterns are banned:

1. `142857`
2. `0588235294117647`
3. `052631578947368421`
4. `0434782608695652173913`
5. `0344827586206896551724137931`
6. `0212765957446808510638297872340425531914893617`
7. `0169491525423728813559322033898305084745762711864406779661`
8. `016393442622950819672131147540983606557377049180327868852459`
9. `010309278350515463917525773195876288659793814432989690721649484536082474226804123711340206185567`

---

## 4. ID Lifecycle

Simple two-state model:

```
AVAILABLE  →  TAKEN
```

- **AVAILABLE** — In pool, ready to be issued.
- **TAKEN** — Issued to a caller; permanently consumed. Never re-issued.

No callback or confirmation from the calling service is required.

---

## 5. Pool Management

- The service maintains a **pre-generated pool** of AVAILABLE IDs per namespace in PostgreSQL.
- **Background replenishment**: A background task monitors pool levels and generates new IDs when the count of AVAILABLE IDs drops below a configurable threshold.
  - `pool_min_threshold` — Trigger generation when AVAILABLE count falls below this (global, same for all namespaces).
  - `pool_generation_batch_size` — Number of IDs to generate per replenishment cycle (global).
  - Both values are configurable; exact numbers to be decided later.
- **No archive table** — At an expected scale of up to 50 million IDs per namespace, a single table with a status column is sufficient.
- **Uniqueness**: Every generated ID is checked against all existing IDs (both AVAILABLE and TAKEN) in its namespace before being added to the pool.

---

## 6. Concurrency & Scalability (Kubernetes)

- Multiple pods can run simultaneously.
- **Issuing IDs**: `SELECT ... FOR UPDATE` row-level locking in PostgreSQL ensures no two pods issue the same ID.
- **Generating IDs**: Database unique constraint on `(namespace, id)` prevents duplicates. If a concurrent insert causes a conflict, the conflicting ID is silently skipped.
- No application-level distributed locks required — the database is the single source of truth.

---

## 7. ID Space Exhaustion

- When a caller requests an ID and the pool is empty **and** no more valid IDs can be generated (full search space exhausted), the service returns a clear error response.
- The error must indicate that the ID space for that namespace is exhausted.
- No warning threshold — only a hard error when fully exhausted.
- **Note**: The effective ID space is significantly smaller than the raw numeric range due to the generation filters. For example, a 10-digit ID starting with 2-9 has a raw space of ~8x10^9, but filters may reduce this to ~40-60% of that.

---

## 8. API Design

Following MOSIP's response wrapper style, adapted with namespace support. All APIs are **OpenAPI 3.1 compliant**. All responses use `Content-Type: application/json`.

### 8.1 OpenAPI Specification

FastAPI auto-generates a machine-readable OpenAPI spec and interactive documentation:

| Path | Description |
|------|-------------|
| `GET /docs` | Swagger UI — interactive API explorer |
| `GET /redoc` | ReDoc — alternative API documentation |
| `GET /openapi.json` | Machine-readable OpenAPI 3.1 JSON spec |

### 8.2 Standard Response Envelope

All endpoints return a consistent MOSIP-style envelope with `Content-Type: application/json`.

**Success**:
```json
{
  "id": "string",
  "version": "string",
  "responsetime": "2026-03-27T10:00:00.000Z",
  "response": { ... },
  "errors": []
}
```

**Error** (`response` is `null`, `errors` is populated):
```json
{
  "id": "string",
  "version": "string",
  "responsetime": "2026-03-27T10:00:00.000Z",
  "response": null,
  "errors": [
    { "errorCode": "IDG-001", "message": "No IDs available for namespace 'farmer_id'" }
  ]
}
```

### 8.3 Path Parameter Constraints

| Parameter | Type | Pattern | Description |
|-----------|------|---------|-------------|
| `{namespace}` | string | `^[a-z][a-z0-9_]{1,63}$` | Lowercase alphanumeric + underscore, starts with letter, max 64 chars |
| `{id}` | string | `^\d{1,32}$` | Digits only, 1–32 characters |

Invalid path parameters are rejected at the routing level with HTTP `422 Unprocessable Entity`.

### 8.4 Endpoints

| Method | Path | Description | Success HTTP Status |
|--------|------|-------------|---------------------|
| `POST` | `/v1/idgenerator/{namespace}/id` | Issue one ID from the namespace pool | `200 OK` |
| `GET` | `/v1/idgenerator/{namespace}/id/validate/{id}` | Validate an ID's structure (checksum + filter rules) | `200 OK` |
| `GET` | `/v1/idgenerator/health` | Health check (DB connectivity) | `200 OK` |
| `GET` | `/v1/idgenerator/version` | Returns service version, build info | `200 OK` |

> **Note on `POST` for Issue ID**: Issuing an ID is a state-changing operation (AVAILABLE → TAKEN). Per HTTP/REST semantics, `GET` must be safe and idempotent. We use `POST` to correctly signal that this operation modifies state. No request body is required — the namespace is specified in the path.

#### Issue ID — `POST /v1/idgenerator/{namespace}/id`

Issues a single AVAILABLE ID from the specified namespace pool and marks it as TAKEN. No request body required.

**Response (HTTP `200 OK`)**:
```json
{
  "id": "mosip.idgenerator",
  "version": "1.0",
  "responsetime": "2026-03-27T10:00:00.000Z",
  "response": {
    "id": "5738201964"
  },
  "errors": []
}
```

**Error responses**:

| Condition | HTTP Status | Error Code |
|-----------|-------------|------------|
| Pool temporarily empty (replenishment in progress) | `503 Service Unavailable` | `IDG-001` |
| ID space permanently exhausted | `410 Gone` | `IDG-002` |
| Unknown namespace | `404 Not Found` | `IDG-003` |

#### Validate ID — `GET /v1/idgenerator/{namespace}/id/validate/{id}`

Validates whether a given ID is **structurally valid** for the specified namespace. This is a purely mathematical/structural check — it verifies:
1. The Verhoeff checksum digit is correct.
2. The ID passes all 10 filter rules for the namespace (correct length, no forbidden sequences, etc.).

It does **not** check whether the ID exists in the database or whether it is AVAILABLE/TAKEN.

**Use case**: A downstream system receives an ID (e.g., typed in by a user on a form) and wants to quickly verify it is not a typo or fabricated number — without needing a database lookup.

**Response (HTTP `200 OK`)** — both valid and invalid IDs return 200; the result is in the body:
```json
{
  "id": "mosip.idgenerator",
  "version": "1.0",
  "responsetime": "2026-03-27T10:00:00.000Z",
  "response": {
    "id": "5738201964",
    "valid": true
  },
  "errors": []
}
```

**Error responses**:

| Condition | HTTP Status | Error Code |
|-----------|-------------|------------|
| Unknown namespace | `404 Not Found` | `IDG-003` |

#### Health Check — `GET /v1/idgenerator/health`

Returns service health (DB connectivity ping). Used as Kubernetes readiness probe.

| Condition | HTTP Status |
|-----------|-------------|
| Healthy (DB reachable, startup complete) | `200 OK` |
| Unhealthy (DB unreachable or startup not complete) | `503 Service Unavailable` |

#### Version — `GET /v1/idgenerator/version`

Returns the service version and build metadata. Used by test frameworks and monitoring to identify which version is deployed. Always returns `200 OK`.

**Response (HTTP `200 OK`)**:
```json
{
  "id": "mosip.idgenerator",
  "version": "1.0",
  "responsetime": "2026-03-28T10:00:00.000Z",
  "response": {
    "service_version": "0.1.0",
    "build_time": "2026-03-28T08:30:00.000Z",
    "git_commit": "a1b2c3d"
  },
  "errors": []
}
```

- `service_version`: Semantic version from `pyproject.toml`.
- `build_time`: Timestamp when the Docker image was built (injected at build time).
- `git_commit`: Short git commit hash (injected at build time).

### 8.5 HTTP Status Code Summary

| HTTP Status | Meaning | When Used |
|-------------|---------|-----------|
| `200 OK` | Request succeeded | Successful issue, validate, health, version |
| `404 Not Found` | Resource not found | Unknown namespace (`IDG-003`) |
| `410 Gone` | Resource permanently unavailable | ID space exhausted (`IDG-002`) |
| `422 Unprocessable Entity` | Validation error | Invalid path parameter format |
| `503 Service Unavailable` | Temporarily unavailable | Pool empty (`IDG-001`), health check failing |

### 8.6 Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `IDG-001` | `503` | No IDs available in pool (temporary — replenishment in progress) |
| `IDG-002` | `410` | ID space exhausted for namespace (permanent — no more IDs possible) |
| `IDG-003` | `404` | Unknown namespace |
| `IDG-004` | — | Invalid ID (returned in validate response body, not as HTTP error) |

---

## 9. Configuration

```yaml
# Global filter rules
id_generator:
  sequence_limit: 3
  repeating_limit: 2
  repeating_block_limit: 2
  conjugative_even_digits_limit: 3
  digits_group_limit: 5
  reverse_digits_group_limit: 5
  not_start_with: ["0", "1"]
  restricted_numbers: []

  # Pool management
  pool_min_threshold: <TBD>
  pool_generation_batch_size: <TBD>

  # Namespaces
  namespaces:
    social_id:
      id_length: 10
    farmer_id:
      id_length: 12
    health_id:
      id_length: 10
```

---

## 10. Database Schema (Conceptual)

One table per namespace, auto-created on startup:

```sql
-- Example for namespace "social_id"
TABLE id_pool_social_id (
    id_value        VARCHAR(32)     PRIMARY KEY,
    status          VARCHAR(16)     NOT NULL DEFAULT 'AVAILABLE',  -- 'AVAILABLE' or 'TAKEN'
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    issued_at       TIMESTAMPTZ     NULL       -- NULL until taken
);

CREATE INDEX idx_social_id_available ON id_pool_social_id (status)
    WHERE status = 'AVAILABLE';
```

- Each namespace gets its own table (`id_pool_{namespace}`).
- No `namespace` column needed — the table name is the namespace.
- Tables are auto-created on startup via `CREATE TABLE IF NOT EXISTS`.

---

## 11. Items Marked TBD

| Item | Status |
|------|--------|
| Audit trail (who fetched each ID) | TBD — not required now |
| Batch fetch API (issue N IDs in one call) | TBD — not required now |
| Pool threshold & batch size exact values | TBD — configurable, decided at deployment |
| Authentication / rate limiting | Not required |

---

## 12. Technology Stack

| Component | Choice |
|-----------|--------|
| Language | Python |
| Framework | FastAPI |
| Database | PostgreSQL |
| Randomness | Python `secrets` module |
| Deployment | Kubernetes (horizontal pod scaling) |

---

## 13. Reference

- MOSIP UIN Generator: [Documentation](https://docs.mosip.io/1.2.0/id-lifecycle-management/supporting-components/commons/id-generator#uin-generation-filters)
- MOSIP UIN Generator Source: `commons/kernel/kernel-idgenerator-service/src/main/java/io/mosip/kernel/uingenerator`
