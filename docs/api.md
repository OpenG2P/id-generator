# ID Generator Service — API Reference

**Version**: 0.1
**Date**: 2026-03-28
**Base Path**: `/v1/idgenerator`

---

## 1. OpenAPI Specification

All APIs are **OpenAPI 3.1 compliant**. FastAPI auto-generates a machine-readable spec and interactive documentation:

| Path | Description |
|------|-------------|
| `GET /docs` | Swagger UI — interactive API explorer |
| `GET /redoc` | ReDoc — alternative API documentation |
| `GET /openapi.json` | Machine-readable OpenAPI 3.1 JSON spec |

---

## 2. Standard Response Envelope

All endpoints return a consistent envelope with `Content-Type: application/json`.

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
    { "errorCode": "IDG-001", "message": "No IDs available for ID type 'farmer_id'" }
  ]
}
```

---

## 3. Path Parameter Constraints

| Parameter | Type | Pattern | Description |
|-----------|------|---------|-------------|
| `{id_type}` | string | `^[a-z][a-z0-9_]{1,63}$` | Lowercase alphanumeric + underscore, starts with letter, max 64 chars |
| `{id}` | string | `^\d{1,32}$` | Digits only, 1–32 characters |

Invalid path parameters are rejected at the routing level with HTTP `422 Unprocessable Entity`.

---

## 4. Endpoints

| Method | Path | Description | Success HTTP Status |
|--------|------|-------------|---------------------|
| `POST` | `/v1/idgenerator/{id_type}/id` | Issue one ID from the ID type pool | `200 OK` |
| `GET` | `/v1/idgenerator/{id_type}/id/validate/{id}` | Validate an ID's structure (checksum + filter rules) | `200 OK` |
| `GET` | `/v1/idgenerator/health` | Health check (DB connectivity) | `200 OK` |
| `GET` | `/v1/idgenerator/version` | Returns service version, build info | `200 OK` |
| `GET` | `/v1/idgenerator/config` | Returns active configuration (ID types, filter rules) | `200 OK` |

---

### 4.1 Issue ID — `POST /v1/idgenerator/{id_type}/id`

Issues a single AVAILABLE ID from the specified ID type pool and marks it as TAKEN. No request body required.

> **Note on `POST`**: Issuing an ID is a state-changing operation (AVAILABLE → TAKEN). Per HTTP/REST semantics, `GET` must be safe and idempotent. We use `POST` to correctly signal that this operation modifies state. No request body is required — the ID type is specified in the path.

**Response (HTTP `200 OK`)**:
```json
{
  "id": "openg2p.idgenerator",
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
| Unknown ID type | `404 Not Found` | `IDG-003` |

---

### 4.2 Validate ID — `GET /v1/idgenerator/{id_type}/id/validate/{id}`

Validates whether a given ID is **structurally valid** for the specified ID type. This is a purely mathematical/structural check — it verifies:
1. The Verhoeff checksum digit is correct.
2. The ID passes all 10 filter rules for the ID type (correct length, no forbidden sequences, etc.).

It does **not** check whether the ID exists in the database or whether it is AVAILABLE/TAKEN.

**Use case**: A downstream system receives an ID (e.g., typed in by a user on a form) and wants to quickly verify it is not a typo or fabricated number — without needing a database lookup.

**Response (HTTP `200 OK`)** — both valid and invalid IDs return 200; the result is in the body:
```json
{
  "id": "openg2p.idgenerator",
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
| Unknown ID type | `404 Not Found` | `IDG-003` |

---

### 4.3 Health Check — `GET /v1/idgenerator/health`

Returns service health (DB connectivity ping). Used as Kubernetes readiness/liveness probe.

| Condition | HTTP Status | Error Code |
|-----------|-------------|------------|
| Healthy (DB reachable, startup complete) | `200 OK` | — |
| Startup not complete | `503 Service Unavailable` | `IDG-005` |
| DB health check failed | `503 Service Unavailable` | `IDG-006` |

---

### 4.4 Version — `GET /v1/idgenerator/version`

Returns the service version and build metadata. Used by test frameworks and monitoring to identify which version is deployed. Always returns `200 OK`.

**Response (HTTP `200 OK`)**:
```json
{
  "id": "openg2p.idgenerator",
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

| Field | Description |
|-------|-------------|
| `service_version` | Semantic version from `pyproject.toml` |
| `build_time` | Timestamp when the Docker image was built (injected at build time) |
| `git_commit` | Short git commit hash (injected at build time) |

---

### 4.5 Config — `GET /v1/idgenerator/config`

Returns the active service configuration including all configured ID types and their ID lengths, plus the global filter rules. Useful for test frameworks and diagnostics to discover configured ID types without hardcoding names.

**Response (HTTP `200 OK`)**:
```json
{
  "id": "openg2p.idgenerator",
  "version": "1.0",
  "responsetime": "2026-03-28T10:00:00.000Z",
  "response": {
    "id_types": {
      "farmer_id": { "id_length": 10 },
      "household_id": { "id_length": 10 }
    },
    "filter_rules": {
      "sequence_limit": 3,
      "repeating_limit": 2,
      "repeating_block_limit": 2,
      "conjugative_even_digits_limit": 3,
      "digits_group_limit": 5,
      "reverse_digits_group_limit": 5,
      "not_start_with": ["0", "1"],
      "restricted_numbers": []
    }
  },
  "errors": []
}
```

---

## 5. HTTP Status Code Summary

| HTTP Status | Meaning | When Used |
|-------------|---------|-----------|
| `200 OK` | Request succeeded | Successful issue, validate, health, version, config |
| `404 Not Found` | Resource not found | Unknown ID type (`IDG-003`) |
| `410 Gone` | Resource permanently unavailable | ID space exhausted (`IDG-002`) |
| `422 Unprocessable Entity` | Validation error | Invalid path parameter format |
| `503 Service Unavailable` | Temporarily unavailable | Pool empty (`IDG-001`), health check failing (`IDG-005`, `IDG-006`) |

---

## 6. Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `IDG-001` | `503` | No IDs available in pool (temporary — replenishment in progress) |
| `IDG-002` | `410` | ID space exhausted for ID type (permanent — no more IDs possible) |
| `IDG-003` | `404` | Unknown ID type |
| `IDG-004` | — | Invalid ID (returned in validate response body, not as HTTP error) |
| `IDG-005` | `503` | Service not ready — startup not complete |
| `IDG-006` | `503` | Database health check failed |
