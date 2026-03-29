# ID Generator Service — Test Plan

**Version**: 0.1
**Date**: 2026-03-28
**Status**: Draft

---

## 1. Test Approach

All tests are **API-level integration tests** executed against a running instance of the ID Generator service. The service can be local (Docker Compose) or a remote deployment (staging/production).

No unit tests or mocking — we test the real service end-to-end through its HTTP API.

---

## 2. Technology Stack

| Component | Choice | License | Rationale |
|-----------|--------|---------|-----------|
| Framework | `pytest` | MIT | Standard Python test framework; markers, parametrize, CLI selection |
| HTTP Client | `httpx` (async) | BSD-3-Clause | Async HTTP calls; matches the async service |
| Async support | `pytest-asyncio` | Apache 2.0 | Run async test functions in pytest |
| Reporting | `pytest-html` + custom plugin | MPL 2.0 | HTML test report with version, timestamp, summary |
| Test ordering | `pytest-ordering` | MIT | Control test execution order across phases |
| Report metadata | `pytest-metadata` | MPL 2.0 | Bundled with pytest-html; populates Environment table |
| Config | CLI options + env vars | — | `--base-url` CLI option or `IDGEN_BASE_URL` env var |

All components use **permissive open-source licenses**. No copyleft (GPL) dependencies.

---

## 3. Project Structure

```
tests/
├── conftest.py                 # Fixtures: base_url, http client, ID type setup
├── report_plugin.py            # Custom pytest plugin for enhanced HTML report
├── pytest.ini                  # Marker registration, default options
├── test_cases.yaml             # Reviewable list of all test cases (human-readable)
├── test_exhaustive.py          # Category 1: Exhaustive uniqueness & randomness
├── test_filters.py             # Category 2: Filter validation on sample IDs
├── test_exhaustion.py          # Category 3: Space exhaustion handling
├── test_performance.py         # Category 4: Response time benchmarks
├── test_api_contract.py        # Category 5: API response format, error codes, edge cases
└── helpers/
    ├── verhoeff.py             # Local Verhoeff implementation for validation
    └── filters.py              # Local filter implementations for cross-checking
```

---

## 4. Configuration

### 4.1 CLI Options

```bash
# Run against local service
pytest --base-url=http://localhost:8000

# Run against remote deployment
pytest --base-url=https://idgen.staging.example.com

# Run specific category
pytest -m exhaustive
pytest -m filters
pytest -m exhaustion
pytest -m performance

# Run a single test
pytest test_exhaustive.py::test_all_ids_unique_id_type_1

# Generate HTML report
pytest --html=report.html
```

### 4.2 Environment Variables (alternative to CLI)

```bash
export IDGEN_BASE_URL=http://localhost:8000
pytest
```

> **Note**: ID type names and ID lengths are **not** configured in the test framework. They are **auto-discovered** from the running service via `GET /v1/idgenerator/config` at the start of each test session. When you change ID types in the service config, tests automatically adapt — no test configuration changes needed.

### 4.3 Pytest Markers

```ini
# pytest.ini
[pytest]
markers =
    exhaustive: Exhaustive uniqueness and randomness tests (small ID space)
    filters: Filter rule validation tests
    exhaustion: Space exhaustion handling tests
    performance: Response time benchmark tests
    api_contract: API format and error handling tests
    slow: Tests that take a long time to run
```

---

## 5. Test Prerequisites

Before running the tests, the target ID Generator service must be configured with **at least three ID types**:

- **Two ID types with a small ID length** (e.g., 5 digits) — used for exhaustive tests that drain the entire ID space.
- **One ID type with a larger ID length** (e.g., 10 digits) — used for performance and filter tests that need a large pool.

Example configuration:
```yaml
id_types:
  farmer_id:
    id_length: 5
  household_id:
    id_length: 5
  test_perf_id:
    id_length: 10
```

The test framework **auto-discovers** ID type names and ID lengths from the service's `GET /v1/idgenerator/config` endpoint at session start. It then automatically selects:
- `id_type_1`: The first ID type with the **smallest** `id_length` (for exhaustive tests).
- `id_type_2`: The second ID type with the **smallest** `id_length` (for ID type independence tests).
- `perf_id_type`: The ID type with the **largest** `id_length` (for performance and filter tests that require long IDs).

**Why small ID length for exhaustive tests?**
- 4 random digits + 1 Verhoeff checksum = 5-digit IDs.
- With `not_start_with: [0, 1]`, the raw candidate space is 8,000 (8 × 10 × 10 × 10).
- After all filters, the valid space is approximately 2,000–4,000 IDs (estimate).
- This is small enough to exhaustively issue every ID via the API in a reasonable time.

**Important**: The small-ID-length ID types should be **dedicated for testing** and not shared with production workloads. Running the exhaustive tests will consume all IDs in those ID types.

---

## 6. Shared Test Fixtures (`conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `base_url` | session | Service URL from CLI option or env var |
| `client` | session | `httpx.AsyncClient` instance with base URL configured |
| `service_config` | session | Fetches and caches config from `GET /v1/idgenerator/config` at session start |
| `id_types` | session | Dict of all configured ID types (from `service_config`) |
| `id_type_1` | session | Auto-selected: first ID type with smallest `id_length` |
| `id_type_2` | session | Auto-selected: second ID type with smallest `id_length` |
| `perf_id_type` | session | Auto-selected: ID type with largest `id_length` |
| `id_type_1_length` | session | ID length configured for `id_type_1` |
| `id_type_2_length` | session | ID length configured for `id_type_2` |
| `perf_id_length` | session | ID length configured for `perf_id_type` |
| `issue_id(client, id_type)` | session | Callable: `POST` Issue ID API, returns httpx response |
| `validate_id(client, id_type, id)` | session | Callable: `GET` Validate ID API, returns httpx response |
| `health_check(client)` | session | Callable: `GET` Health API, returns httpx response |
| `service_version` | session | Fetches and caches version info from `GET /v1/idgenerator/version` at session start |
| `id_type_1_issued_ids` | session | List collecting all IDs issued from `id_type_1` during exhaustive tests |
| `id_type_2_issued_ids` | session | List collecting all IDs issued from `id_type_2` during exhaustive tests |
| `id_type_1_exhausted` | session | Dict tracking whether `id_type_1` has been fully exhausted |
| `id_type_2_exhausted` | session | Dict tracking whether `id_type_2` has been fully exhausted |

---

## 7. Test Cases

### Category 1: Exhaustive Uniqueness & Randomness (`test_exhaustive.py`)

These tests issue **every possible ID** from a small-space ID type (length=5) and verify correctness.

| # | Test ID | Test Name | Description | Marker |
|---|---------|-----------|-------------|--------|
| 1.1 | `EXH-001` | `test_all_ids_unique_ns1` | `POST` Issue IDs from `farmer_id` one at a time until space is exhausted (HTTP `410`/`IDG-002`). Collect all IDs into a list. Assert: no duplicates (length of set == length of list). | `exhaustive`, `slow` |
| 1.2 | `EXH-002` | `test_all_ids_unique_ns2` | Same as EXH-001 but for `household_id`. Verifies ID type isolation — IDs are independently generated. | `exhaustive`, `slow` |
| 1.3 | `EXH-003` | `test_ids_not_sequential_ns1` | Using the list from EXH-001: assert that IDs are NOT in ascending or descending numeric order. Compare the issued order with sorted order — they must differ. | `exhaustive` |
| 1.4 | `EXH-004` | `test_ids_not_sequential_ns2` | Same as EXH-003 for `household_id`. | `exhaustive` |
| 1.5 | `EXH-005` | `test_ids_not_clustered` | Using the list from EXH-001: convert IDs to integers, compute first-order differences (delta between consecutive IDs). Assert that deltas are not constant or near-constant (std deviation of deltas > threshold). | `exhaustive` |
| 1.6 | `EXH-006` | `test_digit_distribution` | Across all issued IDs from EXH-001: for each middle digit position (excluding position 0 and the checksum digit), count frequency of each digit (0-9). Assert no single digit accounts for >50% of occurrences at any position. This catches gross generation bugs while tolerating the inherent bias from filter rules (no repeating digits, no sequences, no consecutive even digits). | `exhaustive` |
| 1.7 | `EXH-007` | `test_id_type_independence` | Compare IDs issued to `farmer_id` and `household_id`. Assert: the **order** of issuance differs (since each ID type generates independently). The sets of IDs may overlap (same valid ID can exist in both ID types), but the issuance order must be different. | `exhaustive` |
| 1.8 | `EXH-008` | `test_total_count_within_expected_range` | Assert that the total number of IDs issued before exhaustion falls within a dynamically computed expected range based on `id_length`. Raw space = `8 * 10^(id_length - 2)`. Expected range: `[5% of raw_space, raw_space]`. Filters typically reduce the raw space to 15-60% depending on ID length and filter parameters. | `exhaustive` |

### Category 2: Filter Validation (`test_filters.py`)

These tests use the **Validate ID API** (`GET /v1/idgenerator/{id_type}/id/validate/{id}`) to verify that filters accept/reject IDs correctly. No IDs are consumed from the pool.

Additionally, all IDs collected during the exhaustive tests are cross-checked.

| # | Test ID | Test Name | Description | Marker |
|---|---------|-----------|-------------|--------|
| 2.1 | `FLT-001` | `test_valid_id_passes_validation` | Construct a known-valid ID (manually compute Verhoeff checksum, ensure all filters pass). Submit to Validate API. Assert `valid: true`. | `filters` |
| 2.2 | `FLT-002` | `test_wrong_checksum_rejected` | Take a valid ID, change the last digit (checksum) to an incorrect value. Assert `valid: false`. | `filters` |
| 2.3 | `FLT-003` | `test_starts_with_zero_rejected` | Construct an ID starting with `0`. Assert `valid: false`. | `filters` |
| 2.4 | `FLT-004` | `test_starts_with_one_rejected` | Construct an ID starting with `1`. Assert `valid: false`. | `filters` |
| 2.5 | `FLT-005` | `test_ascending_sequence_rejected` | Construct an ID containing ascending sequence beyond limit (e.g., `X1234X` with limit=3). Assert `valid: false`. | `filters` |
| 2.6 | `FLT-006` | `test_descending_sequence_rejected` | Construct an ID containing descending sequence beyond limit (e.g., `X9876X`). Assert `valid: false`. | `filters` |
| 2.7 | `FLT-007` | `test_repeating_digit_rejected` | Construct an ID with repeating digit within limit distance (e.g., `X11X` or `X1Y1X` with limit=2). Assert `valid: false`. | `filters` |
| 2.8 | `FLT-008` | `test_repeating_block_rejected` | Construct an ID with repeated digit block (e.g., `48XX48`). Assert `valid: false`. | `filters` |
| 2.9 | `FLT-009` | `test_conjugative_even_digits_rejected` | Construct an ID with N consecutive even digits (e.g., `X2468X` with limit=3). Assert `valid: false`. | `filters` |
| 2.10 | `FLT-010` | `test_first_equals_last_rejected` | Construct an ID where first N digits equal last N digits. Assert `valid: false`. | `filters` |
| 2.11 | `FLT-011` | `test_first_equals_reverse_last_rejected` | Construct an ID where first N digits equal reverse of last N digits. Assert `valid: false`. | `filters` |
| 2.12 | `FLT-012` | `test_restricted_number_rejected` | Configure a restricted number, construct an ID containing it. Assert `valid: false`. | `filters` |
| 2.13 | `FLT-013` | `test_cyclic_number_rejected` | Construct an ID containing cyclic number `142857` (the shortest one). Assert `valid: false`. Requires ID length >= 7. | `filters` |
| 2.14 | `FLT-014` | `test_wrong_length_rejected` | Submit an ID with incorrect length for the ID type. Assert `valid: false`. | `filters` |
| 2.15 | `FLT-015` | `test_all_exhaustive_ids_pass_validation` | Take all IDs collected from EXH-001. Submit each to the Validate API. Assert **every one** returns `valid: true`. This cross-checks that the generator and validator agree. | `filters`, `slow` |
| 2.16 | `FLT-016` | `test_boundary_sequence_allowed` | Construct an ID with a sequence exactly at the limit (e.g., `X12X` with limit=3 → "12" is length 2, allowed). Assert `valid: true`. | `filters` |
| 2.17 | `FLT-017` | `test_boundary_repeating_allowed` | Construct an ID where same digit appears but beyond the limit distance. Assert `valid: true`. | `filters` |
| 2.18 | `FLT-018` | `test_non_numeric_rejected` | Submit IDs containing alphabetic or special characters. Assert `valid: false`. | `filters` |

### Category 3: Space Exhaustion (`test_exhaustion.py`)

These tests verify correct behavior when the ID space is fully consumed.

| # | Test ID | Test Name | Description | Marker |
|---|---------|-----------|-------------|--------|
| 3.1 | `EXS-001` | `test_exhaustion_returns_error` | After EXH-001 has consumed all IDs in `farmer_id`, `POST` one more Issue ID. Assert: HTTP `410 Gone`, error code `IDG-002` with appropriate message. | `exhaustion` |
| 3.2 | `EXS-002` | `test_exhaustion_error_is_permanent` | After EXS-001, `POST` another Issue ID from the same ID type. Assert: still HTTP `410`, `IDG-002` (not a transient error). | `exhaustion` |
| 3.3 | `EXS-003` | `test_other_id_type_unaffected` | After `farmer_id` is exhausted, `POST` Issue ID from `household_id` (if not yet exhausted). Assert: HTTP `200`, succeeds normally. ID types are independent. | `exhaustion` |
| 3.4 | `EXS-004` | `test_exhaustion_response_format` | Verify the exhaustion error response matches the standard error envelope: HTTP `410`, `Content-Type: application/json`, `response` is `null`, `errors` array contains `errorCode` and `message`. | `exhaustion` |

### Category 4: Response Time (`test_performance.py`)

These tests measure API response latency. They should run against an ID type with a healthy pool (NOT the exhausted test ID types). Requires a separate ID type (e.g., `test_perf_id`) with a larger ID length (e.g., 10) so the pool doesn't run out during testing.

| # | Test ID | Test Name | Description | Marker |
|---|---------|-----------|-------------|--------|
| 4.1 | `PRF-001` | `test_issue_id_response_time` | Issue 100 IDs sequentially. Record response time for each. Assert: p50 < 100ms, p95 < 500ms, p99 < 1000ms. (Thresholds are configurable.) | `performance` |
| 4.2 | `PRF-002` | `test_issue_id_concurrent_response_time` | Issue 50 IDs concurrently (asyncio.gather). Record wall-clock time. Assert: total time < threshold. Verifies `SKIP LOCKED` doesn't degrade under concurrency. | `performance` |
| 4.3 | `PRF-003` | `test_validate_id_response_time` | Validate 100 IDs sequentially. Record response time for each. Assert: p50 < 50ms, p95 < 200ms. (Validation is compute-only, no DB write, should be faster.) | `performance` |
| 4.4 | `PRF-004` | `test_health_endpoint_response_time` | Call health endpoint 50 times. Assert: p95 < 200ms. | `performance` |

### Category 5: API Contract (`test_api_contract.py`)

These tests verify OpenAPI compliance, HTTP status codes, response structure, error codes, and edge cases.

| # | Test ID | Test Name | Description | Marker |
|---|---------|-----------|-------------|--------|
| 5.1 | `API-001` | `test_issue_response_envelope` | `POST` to Issue ID. Assert: HTTP `200`, `Content-Type: application/json`, response has `id`, `version`, `responsetime` (ISO 8601 format), `response.id` (string of digits), `errors` (empty list). | `api_contract` |
| 5.2 | `API-002` | `test_validate_response_envelope` | `GET` Validate ID. Assert: HTTP `200`, `Content-Type: application/json`, response has `id`, `version`, `responsetime`, `response.id`, `response.valid` (boolean), `errors`. | `api_contract` |
| 5.3 | `API-003` | `test_unknown_id_type_returns_404` | `POST` to Issue ID with a non-existent ID type. Assert: HTTP `404`, error code `IDG-003`, `response` is `null`. | `api_contract` |
| 5.4 | `API-004` | `test_validate_unknown_id_type_returns_404` | `GET` Validate ID with a non-existent ID type. Assert: HTTP `404`, error code `IDG-003`. | `api_contract` |
| 5.5 | `API-005` | `test_health_endpoint_returns_healthy` | `GET` Health. Assert: HTTP `200`, response indicates healthy. | `api_contract` |
| 5.6 | `API-006` | `test_issued_id_is_numeric` | `POST` to Issue ID. Assert: the returned ID string contains only digits (regex `^\d+$`). | `api_contract` |
| 5.7 | `API-007` | `test_issued_id_correct_length` | `POST` to Issue ID. Assert: length matches the ID type configuration. | `api_contract` |
| 5.8 | `API-008` | `test_issued_id_passes_validation` | `POST` to Issue ID, then `GET` Validate. Assert: `valid: true`. | `api_contract` |
| 5.9 | `API-009` | `test_version_endpoint` | `GET` Version. Assert: HTTP `200`, response contains `service_version` (semver format), `build_time`, `git_commit`. | `api_contract` |
| 5.10 | `API-010` | `test_version_response_envelope` | Verify the version response follows the standard response envelope: `id`, `version`, `responsetime`, `response`, `errors`. | `api_contract` |
| 5.11 | `API-011` | `test_issue_id_get_not_allowed` | `GET` (not `POST`) to Issue ID endpoint. Assert: HTTP `405 Method Not Allowed`. Confirms only `POST` is accepted. | `api_contract` |
| 5.12 | `API-012` | `test_invalid_id_type_format_returns_422` | `POST` to Issue ID with an invalid ID type format (e.g., `123invalid`, `UPPER`, `ns with spaces`). Assert: HTTP `422 Unprocessable Entity`. | `api_contract` |
| 5.13 | `API-013` | `test_invalid_id_format_returns_422` | `GET` Validate with an invalid ID format (e.g., `abc`, `12.34`). Assert: HTTP `422 Unprocessable Entity`. | `api_contract` |
| 5.14 | `API-014` | `test_openapi_spec_available` | `GET /openapi.json`. Assert: HTTP `200`, response is valid JSON with `openapi` field starting with `3.`. | `api_contract` |
| 5.15 | `API-015` | `test_content_type_json` | Call each endpoint. Assert: all responses include `Content-Type: application/json` header. | `api_contract` |

---

## 8. Test Report

### 8.1 Overview

Every test run produces an **HTML report** viewable in any browser. The report is self-contained (single file, no external dependencies) and includes all the information needed to understand what was tested and the results.

### 8.2 Report Contents

The report includes the following sections:

**Header / Metadata:**

| Field | Source | Description |
|-------|--------|-------------|
| Service Version | `GET /v1/idgenerator/version` → `service_version` | Semver of the tested service (e.g., `0.1.0`) |
| Git Commit | `GET /v1/idgenerator/version` → `git_commit` | Short commit hash of the tested build |
| Build Time | `GET /v1/idgenerator/version` → `build_time` | When the tested build was created |
| Target URL | `--base-url` CLI option | The service URL tested against |
| Test Run Date/Time | Auto-captured at start of test session | When the tests were executed (ISO 8601) |
| Test Run Duration | Auto-captured | Total wall-clock time for the full suite |

**Summary:**

| Metric | Description |
|--------|-------------|
| Total tests | Count of all tests executed |
| Passed | Count + percentage |
| Failed | Count + percentage |
| Skipped | Count + percentage |
| Errors | Count (tests that errored, not assertion failures) |

**Per-category breakdown:**

| Category | Passed | Failed | Skipped | Duration |
|----------|--------|--------|---------|----------|
| Exhaustive | 7/8 | 1/8 | 0 | 3m 42s |
| Filters | 18/18 | 0/18 | 0 | 4s |
| ... | | | | |

**Detailed results:**
- Each test case listed with: Test ID, name, status (PASS/FAIL/SKIP), duration, and failure details (if any).
- Failed tests show the assertion error and relevant context.

### 8.3 Implementation

The report is generated by a **custom pytest plugin** (`tests/report_plugin.py`) that:

1. **On session start**: Calls `GET /v1/idgenerator/version` to fetch service metadata. If the version endpoint is unreachable, fields are marked as `"unknown"`.
2. **During tests**: Collects per-test results, timing, and failure details.
3. **On session end**: Generates the HTML report using `pytest-html` as the base, with custom header metadata injected via `pytest_html_report_title` and `pytest_html_results_summary` hooks.

### 8.4 Report Generation

```bash
# Generate report (default filename: report.html)
pytest --base-url=http://localhost:8000 --html=report.html --self-contained-html

# Custom report filename
pytest --base-url=http://localhost:8000 --html=idgen-test-report-2026-03-28.html --self-contained-html
```

### 8.5 Sample Report Header

```
╔══════════════════════════════════════════════════════════╗
║  ID Generator — Test Report                              ║
╠══════════════════════════════════════════════════════════╣
║  Service Version:   0.1.0                                ║
║  Git Commit:        a1b2c3d                              ║
║  Build Time:        2026-03-28T08:30:00.000Z             ║
║  Target URL:        https://idgen.staging.example.com    ║
║  Test Run:          2026-03-28T14:22:00.000Z             ║
║  Duration:          4m 18s                               ║
╠══════════════════════════════════════════════════════════╣
║  TOTAL: 49  |  PASSED: 47  |  FAILED: 1  |  SKIPPED: 1  ║
╚══════════════════════════════════════════════════════════╝
```

---

## 9. Test Execution Order and Dependencies

Some tests have dependencies (e.g., exhaustion tests require all IDs to have been issued first). pytest ordering:

```
Phase 1: API contract tests (api_contract)
    → Verifies service is up and API format is correct
    → Consumes only a few IDs

Phase 2: Filter validation tests (filters)
    → Uses Validate API (no IDs consumed) except FLT-015
    → FLT-015 runs after exhaustive tests

Phase 3: Exhaustive tests (exhaustive)
    → Issues ALL IDs from ID types farmer_id and household_id
    → Collects IDs into session-scoped fixtures for later use
    → This is the longest phase

Phase 4: Exhaustion tests (exhaustion)
    → Depends on Phase 3 having consumed all IDs
    → Must run after exhaustive tests

Phase 5: Performance tests (performance)
    → Runs against a separate performance ID type (test_perf_id)
    → Independent of other phases
```

We use `pytest-ordering` with `@pytest.mark.order()` to enforce this sequence.

### Async Event Loop

All tests and session-scoped async fixtures (HTTP client, service config) share
a **single session-scoped event loop** via:
- `asyncio_default_fixture_loop_scope = session` in `pytest.ini`
- `@pytest_asyncio.fixture(scope="session", loop_scope="session")` on async fixtures
- `@pytest.mark.asyncio(loop_scope="session")` on all test modules

This prevents "event loop is closed" and "bound to a different event loop" errors
that occur when session-scoped async resources (like `httpx.AsyncClient`) are
accessed from function-scoped event loops.

---

## 9. Running Tests

All tests must be run from the `tests/` directory.

### 9.1 Fast Tests (~2 seconds)

```bash
cd tests

# API contract + filters + performance (non-destructive, can run repeatedly)
pytest -m "api_contract or filters or performance" --base-url=http://localhost:8000 -v
```

### 9.2 Full Suite (all phases in order)

```bash
# All tests against local service with HTML report
pytest --base-url=http://localhost:8000 --html=report.html --self-contained-html -v

# All tests against remote service
pytest --base-url=https://idgen.staging.example.com --html=report.html --self-contained-html -v
```

### 9.3 By Category

```bash
pytest -m api_contract --base-url=http://localhost:8000 -v     # API format & errors
pytest -m filters --base-url=http://localhost:8000 -v          # Filter validation
pytest -m exhaustive --base-url=http://localhost:8000 -v       # Drain all IDs (slow)
pytest -m exhaustion --base-url=http://localhost:8000 -v       # Post-exhaustion checks
pytest -m performance --base-url=http://localhost:8000 -v      # Response time benchmarks
pytest -m "not slow" --base-url=http://localhost:8000 -v       # Exclude slow tests
```

### 9.4 Individual Tests

```bash
# Single test by name
pytest -k "test_all_ids_unique_ns1" --base-url=http://localhost:8000

# Single test file
pytest test_filters.py --base-url=http://localhost:8000
```

### 9.5 With Verbose Timing

```bash
pytest -m performance --base-url=http://localhost:8000 -v --tb=short --durations=10
```

---

## 10. Test ID Types Required

Tests **auto-discover** ID types from the service via `GET /v1/idgenerator/config`.
No ID type names are hardcoded in tests. The service must have at least:

- **2 ID types with small `id_length`** (e.g., 5) — used for exhaustive tests
- **1 ID type with large `id_length`** (e.g., 10+) — used for performance tests

**Warning**: Running the exhaustive tests will permanently consume ALL IDs in the
two smallest-length ID types. These ID types must be reset (drop tables and
restart the service) before re-running.

### Conditionally Skipped Tests

| Test | Skip condition | How to enable |
|------|----------------|---------------|
| FLT-010 (first=last) | `id_length < 2 * digits_group_limit + 1` | Use ID type with `id_length >= 11` (for default limit=5) |
| FLT-011 (first=reverse last) | `id_length < 2 * reverse_digits_group_limit + 1` | Same as above |
| FLT-012 (restricted numbers) | `restricted_numbers` is empty | Add entries to `restricted_numbers` in config |
| FLT-015 (cross-validate) | Exhaustive tests haven't run | Run as part of the full suite, not in isolation |

---

## 11. Test Data Management

### 11.1 Session-Scoped Collection

IDs issued during exhaustive tests are stored in session-scoped pytest fixtures:

```python
@pytest.fixture(scope="session")
def id_type_1_issued_ids():
    """Populated by EXH-001. List of all IDs issued from id_type_1, in order."""
    return []
```

This allows later tests (FLT-015, EXH-003, etc.) to reuse the collected data without re-issuing.

### 11.2 Test Reset

To re-run exhaustive tests, the test ID types must be reset. This can be done by:
1. Restarting the service with the test ID types in config (tables are re-created if dropped).
2. Or providing a test setup script that truncates/drops the test tables.

---

## 12. Local Verhoeff & Filter Helpers

The `tests/helpers/` directory contains a **local Python implementation** of the Verhoeff algorithm and all 10 filters. These are used by filter tests (Category 2) to:
- Construct known-valid IDs for positive test cases.
- Construct known-invalid IDs for negative test cases.
- Cross-validate that the service's Validate API agrees with the local implementation.

These helpers are **independent of the service code** — they are a second implementation for cross-checking.

---

## 13. Summary: Test Count

| Category | Test Count | Speed | Pool Impact |
|----------|-----------|-------|-------------|
| Exhaustive (uniqueness & randomness) | 8 | Slow (~minutes) | Consumes all IDs in farmer_id, household_id |
| Filters (validation rules) | 18 | Fast (seconds) | None (uses Validate API), except FLT-015 |
| Exhaustion (error handling) | 4 | Fast (seconds) | Requires prior exhaustion |
| Performance (response time) | 4 | Medium (~30s) | Consumes ~200 IDs from test_perf_id |
| API Contract (OpenAPI, HTTP status, format, errors, version) | 15 | Fast (seconds) | Consumes ~3 IDs |
| **Total** | **49** | | |
