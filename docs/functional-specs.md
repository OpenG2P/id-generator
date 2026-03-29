# ID Generator Service — Functional Specification

**Version**: 0.1
**Date**: 2026-03-27
**Status**: Draft

---

## 1. Overview

A FastAPI-based service that generates unique, random numeric IDs for multiple consuming applications (social ID, farmer ID, family ID, health ID, etc.). Each application operates within its own **ID type**, with an independent pool of pre-generated IDs. The service is designed to be horizontally scalable on Kubernetes.

**Reference**: The ID generation filters are inspired by [MOSIP UIN Generator](https://docs.mosip.io/1.2.0/id-lifecycle-management/supporting-components/commons/id-generator#uin-generation-filters).

---

## 2. ID Type / Realm

- Each consuming application is assigned an **ID type** (e.g., `social_id`, `farmer_id`, `health_id`).
- ID types are **pre-configured** (via config file / environment), not created via API.
- Each ID type has **one configurable parameter: ID length** (up to 32 digits).
- All ID generation/filter rules are **global** (same across all ID types).
- The **same numeric ID may exist in multiple ID types** — pools are fully independent.

### 2.1 Adding an ID Type

- Add the new ID type to the configuration file (YAML / Helm values).
- Perform a rolling restart of pods (e.g., `kubectl rollout restart` or Helm upgrade).
- On startup, the service auto-creates the database table for the new ID type (`CREATE TABLE IF NOT EXISTS`). Existing ID type tables are untouched — all previously generated and issued IDs are fully preserved.
- The service blocks until the minimum pool is generated for the new ID type, then begins serving requests.

### 2.2 Removing an ID Type

- Remove the ID type from the configuration file and restart pods.
- The service will no longer serve requests for the removed ID type — it returns `IDG-003 Unknown ID type`.
- The database table for the removed ID type is **not** automatically dropped. This is a safety measure — a configuration typo should not wipe millions of IDs.
- If storage reclaim is needed, a DBA can manually drop the orphaned table.

---

## 3. ID Generation Rules

### 3.1 Structure

- **Numeric only** — no alphabets or special characters.
- **Length**: Configurable per ID type, maximum 32 digits.
- **Last digit**: Verhoeff checksum — the generator produces `(length - 1)` random digits and appends 1 checksum digit.
- **Randomness**: Python `secrets` module (cryptographically secure). No periodic re-seeding needed.

### 3.2 Filters (All Must Pass)

Every generated ID must pass **all 10 filters**. Filter threshold parameters are globally configurable.

| # | Filter | Description | Config Key |
|---|--------|-------------|------------|
| 1 | **Length** | ID must be exactly the configured length for its ID type | Per-ID-type `id_length` |
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

- The service maintains a **pre-generated pool** of AVAILABLE IDs per ID type in PostgreSQL.
- **Background replenishment**: A background task monitors pool levels and generates new IDs when the count of AVAILABLE IDs drops below a configurable threshold.
  - `pool_min_threshold` — Trigger generation when AVAILABLE count falls below this (global, same for all ID types).
  - `pool_generation_batch_size` — Number of IDs to generate per replenishment cycle (global).
  - Both values are configurable; exact numbers to be decided later.
- **No archive table** — At an expected scale of up to 50 million IDs per ID type, a single table with a status column is sufficient.
- **Uniqueness**: Every generated ID is checked against all existing IDs (both AVAILABLE and TAKEN) in its ID type before being added to the pool.

---

## 6. Concurrency & Scalability (Kubernetes)

- Multiple pods can run simultaneously.
- **Issuing IDs**: `SELECT ... FOR UPDATE` row-level locking in PostgreSQL ensures no two pods issue the same ID.
- **Generating IDs**: Database unique constraint on `(id_type, id)` prevents duplicates. If a concurrent insert causes a conflict, the conflicting ID is silently skipped.
- No application-level distributed locks required — the database is the single source of truth.

---

## 7. ID Space Exhaustion

- When a caller requests an ID and the pool is empty **and** no more valid IDs can be generated (full search space exhausted), the service returns a clear error response.
- The error must indicate that the ID space for that ID type is exhausted.
- No warning threshold — only a hard error when fully exhausted.
- **Note**: The effective ID space is significantly smaller than the raw numeric range due to the generation filters. The raw space is `8 × 10^(id_length - 2)` (first digit restricted to 2-9, last digit is checksum). Filters typically reduce this to 15-60% depending on ID length and filter parameters. Shorter IDs are more heavily constrained. An estimation of the effective space size after filters is available in the table below.

### Estimated ID space by length (after filters)

These estimates were generated using `scripts/space_estimator.py`.

| ID Length (digits) | Estimated Valid IDs |
|--------------------|---------------------|
| 6                  | 35,919              |
| 7                  | 244,348             |
| 8                  | 2,382,981           |
| 9                  | 16,379,411          |
| 10                 | 164,804,199         |
| 11                 | 1,621,760,763       |
| 12                 | 15,716,806,211      |
| 13                 | 149,894,769,328     |
| 14                 | 1,416,056,507,189   |
| 15                 | 13,285,071,919,224  |
| 16                 | 123,889,361,047,011 |

---

## 8. API Design

For the complete API reference — endpoints, request/response formats, response envelope, error codes, and HTTP status codes — see **[API Reference](api.md)**.

**Summary of endpoints**:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/idgenerator/{id_type}/id` | Issue one ID from the ID type pool |
| `GET` | `/v1/idgenerator/{id_type}/id/validate/{id}` | Validate an ID's structure (checksum + filter rules) |
| `GET` | `/v1/idgenerator/health` | Health check (DB connectivity) |
| `GET` | `/v1/idgenerator/version` | Returns service version, build info |
| `GET` | `/v1/idgenerator/config` | Returns active configuration (ID types, filter rules) |

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

  # ID types
  id_types:
    social_id:
      id_length: 10
    farmer_id:
      id_length: 12
    health_id:
      id_length: 10
```

---

## 10. Database Schema (Conceptual)

One table per ID type, auto-created on startup:

```sql
-- Example for ID type "social_id"
TABLE id_pool_social_id (
    id_value        VARCHAR(32)     PRIMARY KEY,
    status          VARCHAR(16)     NOT NULL DEFAULT 'AVAILABLE',  -- 'AVAILABLE' or 'TAKEN'
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    issued_at       TIMESTAMPTZ     NULL       -- NULL until taken
);

CREATE INDEX idx_social_id_available ON id_pool_social_id (status)
    WHERE status = 'AVAILABLE';
```

- Each ID type gets its own table (`id_pool_{id_type}`).
- No `id_type` column needed — the table name is the ID type.
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

- ID generation filters inspired by: [MOSIP UIN Generator](https://docs.mosip.io/1.2.0/id-lifecycle-management/supporting-components/commons/id-generator#uin-generation-filters)
