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
| Timing | `pytest-benchmark` | Apache 2.0 | Response time measurements |
| Config | CLI options + env vars | — | `--base-url`, `--namespace`, etc. |

All components use **permissive open-source licenses**. No copyleft (GPL) dependencies.

---

## 3. Project Structure

```
tests/
├── conftest.py                 # Fixtures: base_url, http client, namespace setup
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
pytest test_exhaustive.py::test_all_ids_unique_namespace_1

# Generate HTML report
pytest --html=report.html
```

### 4.2 Environment Variables (alternative to CLI)

```bash
export IDGEN_BASE_URL=http://localhost:8000
export IDGEN_TEST_NAMESPACE_1=test_ns_1
export IDGEN_TEST_NAMESPACE_2=test_ns_2
pytest
```

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

Before running the tests, the target ID Generator service must be configured with **two test namespaces** using a short ID length:

```yaml
# Test-specific namespace config (added to service config)
namespaces:
  test_ns_1:
    id_length: 5
  test_ns_2:
    id_length: 5
```

**Why length 5?**
- 4 random digits + 1 Verhoeff checksum = 5-digit IDs.
- With `not_start_with: [0, 1]`, the raw candidate space is 8,000 (8 × 10 × 10 × 10).
- After all filters, the valid space is approximately 2,000–4,000 IDs (estimate).
- This is small enough to exhaustively issue every ID via the API in a reasonable time.

**Important**: These test namespaces should be **dedicated for testing** and not shared with production workloads. Running the exhaustive tests will consume all IDs in the namespace.

---

## 6. Shared Test Fixtures (`conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `base_url` | session | Service URL from CLI option or env var |
| `client` | session | `httpx.AsyncClient` instance with base URL configured |
| `namespace_1` | session | Name of first test namespace (default: `test_ns_1`) |
| `namespace_2` | session | Name of second test namespace (default: `test_ns_2`) |
| `issue_id(namespace)` | function | Helper: calls `POST` Issue ID API, returns the ID string |
| `validate_id(namespace, id)` | function | Helper: calls `GET` Validate ID API, returns response |
| `health_check()` | function | Helper: calls Health API, asserts healthy |
| `service_version` | session | Fetches and caches version info from `/v1/idgenerator/version` at session start |

---

## 7. Test Cases

### Category 1: Exhaustive Uniqueness & Randomness (`test_exhaustive.py`)

These tests issue **every possible ID** from a small-space namespace (length=5) and verify correctness.

| # | Test ID | Test Name | Description | Marker |
|---|---------|-----------|-------------|--------|
| 1.1 | `EXH-001` | `test_all_ids_unique_ns1` | `POST` Issue IDs from `test_ns_1` one at a time until space is exhausted (HTTP `410`/`IDG-002`). Collect all IDs into a list. Assert: no duplicates (length of set == length of list). | `exhaustive`, `slow` |
| 1.2 | `EXH-002` | `test_all_ids_unique_ns2` | Same as EXH-001 but for `test_ns_2`. Verifies namespace isolation — IDs are independently generated. | `exhaustive`, `slow` |
| 1.3 | `EXH-003` | `test_ids_not_sequential_ns1` | Using the list from EXH-001: assert that IDs are NOT in ascending or descending numeric order. Compare the issued order with sorted order — they must differ. | `exhaustive` |
| 1.4 | `EXH-004` | `test_ids_not_sequential_ns2` | Same as EXH-003 for `test_ns_2`. | `exhaustive` |
| 1.5 | `EXH-005` | `test_ids_not_clustered` | Using the list from EXH-001: convert IDs to integers, compute first-order differences (delta between consecutive IDs). Assert that deltas are not constant or near-constant (std deviation of deltas > threshold). | `exhaustive` |
| 1.6 | `EXH-006` | `test_digit_distribution` | Across all issued IDs from EXH-001: for each digit position, count frequency of each digit (0-9). Apply chi-squared goodness-of-fit test. No single digit should dominate any position beyond statistical expectation. Note: position 0 will have non-uniform distribution (only 2-9) — adjust expected frequencies accordingly. | `exhaustive` |
| 1.7 | `EXH-007` | `test_namespace_independence` | Compare IDs issued to `test_ns_1` and `test_ns_2`. Assert: the **order** of issuance differs (since each namespace generates independently). The sets of IDs may overlap (same valid ID can exist in both namespaces), but the issuance order must be different. | `exhaustive` |
| 1.8 | `EXH-008` | `test_total_count_within_expected_range` | Assert that the total number of IDs issued before exhaustion falls within the expected range. For 5-digit IDs with standard filters, estimate the valid space mathematically and assert: `expected_min <= count <= expected_max`. | `exhaustive` |

### Category 2: Filter Validation (`test_filters.py`)

These tests use the **Validate ID API** (`GET /v1/idgenerator/{namespace}/id/validate/{id}`) to verify that filters accept/reject IDs correctly. No IDs are consumed from the pool.

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
| 2.14 | `FLT-014` | `test_wrong_length_rejected` | Submit an ID with incorrect length for the namespace. Assert `valid: false`. | `filters` |
| 2.15 | `FLT-015` | `test_all_exhaustive_ids_pass_validation` | Take all IDs collected from EXH-001. Submit each to the Validate API. Assert **every one** returns `valid: true`. This cross-checks that the generator and validator agree. | `filters`, `slow` |
| 2.16 | `FLT-016` | `test_boundary_sequence_allowed` | Construct an ID with a sequence exactly at the limit (e.g., `X12X` with limit=3 → "12" is length 2, allowed). Assert `valid: true`. | `filters` |
| 2.17 | `FLT-017` | `test_boundary_repeating_allowed` | Construct an ID where same digit appears but beyond the limit distance. Assert `valid: true`. | `filters` |
| 2.18 | `FLT-018` | `test_non_numeric_rejected` | Submit IDs containing alphabetic or special characters. Assert `valid: false`. | `filters` |

### Category 3: Space Exhaustion (`test_exhaustion.py`)

These tests verify correct behavior when the ID space is fully consumed.

| # | Test ID | Test Name | Description | Marker |
|---|---------|-----------|-------------|--------|
| 3.1 | `EXS-001` | `test_exhaustion_returns_error` | After EXH-001 has consumed all IDs in `test_ns_1`, `POST` one more Issue ID. Assert: HTTP `410 Gone`, error code `IDG-002` with appropriate message. | `exhaustion` |
| 3.2 | `EXS-002` | `test_exhaustion_error_is_permanent` | After EXS-001, `POST` another Issue ID from the same namespace. Assert: still HTTP `410`, `IDG-002` (not a transient error). | `exhaustion` |
| 3.3 | `EXS-003` | `test_other_namespace_unaffected` | After `test_ns_1` is exhausted, `POST` Issue ID from `test_ns_2` (if not yet exhausted). Assert: HTTP `200`, succeeds normally. Namespaces are independent. | `exhaustion` |
| 3.4 | `EXS-004` | `test_exhaustion_response_format` | Verify the exhaustion error response matches the standard MOSIP error envelope: HTTP `410`, `Content-Type: application/json`, `response` is `null`, `errors` array contains `errorCode` and `message`. | `exhaustion` |

### Category 4: Response Time (`test_performance.py`)

These tests measure API response latency. They should run against a namespace with a healthy pool (NOT the exhausted test namespaces). Requires a separate namespace (e.g., `test_perf_ns`) with a larger ID length (e.g., 10) so the pool doesn't run out during testing.

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
| 5.3 | `API-003` | `test_unknown_namespace_returns_404` | `POST` to Issue ID with a non-existent namespace. Assert: HTTP `404`, error code `IDG-003`, `response` is `null`. | `api_contract` |
| 5.4 | `API-004` | `test_validate_unknown_namespace_returns_404` | `GET` Validate ID with a non-existent namespace. Assert: HTTP `404`, error code `IDG-003`. | `api_contract` |
| 5.5 | `API-005` | `test_health_endpoint_returns_healthy` | `GET` Health. Assert: HTTP `200`, response indicates healthy. | `api_contract` |
| 5.6 | `API-006` | `test_issued_id_is_numeric` | `POST` to Issue ID. Assert: the returned ID string contains only digits (regex `^\d+$`). | `api_contract` |
| 5.7 | `API-007` | `test_issued_id_correct_length` | `POST` to Issue ID. Assert: length matches the namespace configuration. | `api_contract` |
| 5.8 | `API-008` | `test_issued_id_passes_validation` | `POST` to Issue ID, then `GET` Validate. Assert: `valid: true`. | `api_contract` |
| 5.9 | `API-009` | `test_version_endpoint` | `GET` Version. Assert: HTTP `200`, response contains `service_version` (semver format), `build_time`, `git_commit`. | `api_contract` |
| 5.10 | `API-010` | `test_version_response_envelope` | Verify the version response follows the standard MOSIP envelope: `id`, `version`, `responsetime`, `response`, `errors`. | `api_contract` |
| 5.11 | `API-011` | `test_issue_id_get_not_allowed` | `GET` (not `POST`) to Issue ID endpoint. Assert: HTTP `405 Method Not Allowed`. Confirms only `POST` is accepted. | `api_contract` |
| 5.12 | `API-012` | `test_invalid_namespace_format_returns_422` | `POST` to Issue ID with an invalid namespace format (e.g., `123invalid`, `UPPER`, `ns with spaces`). Assert: HTTP `422 Unprocessable Entity`. | `api_contract` |
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
    → Issues ALL IDs from test_ns_1 and test_ns_2
    → Collects IDs into session-scoped fixtures for later use
    → This is the longest phase

Phase 4: Exhaustion tests (exhaustion)
    → Depends on Phase 3 having consumed all IDs
    → Must run after exhaustive tests

Phase 5: Performance tests (performance)
    → Runs against a separate performance namespace (test_perf_ns)
    → Independent of other phases
```

We use `pytest-ordering` or explicit fixture dependencies to enforce this sequence.

---

## 9. Running Tests

### 9.1 Full Suite

```bash
# All tests against local service
pytest --base-url=http://localhost:8000 --html=report.html -v

# All tests against remote service
pytest --base-url=https://idgen.staging.example.com --html=report.html -v
```

### 9.2 By Category

```bash
# Only exhaustive tests
pytest -m exhaustive --base-url=http://localhost:8000

# Only filter tests (fast, no pool consumption)
pytest -m filters --base-url=http://localhost:8000

# Only performance tests
pytest -m performance --base-url=http://localhost:8000

# Exclude slow tests
pytest -m "not slow" --base-url=http://localhost:8000
```

### 9.3 Individual Tests

```bash
# Single test by name
pytest -k "test_all_ids_unique_ns1" --base-url=http://localhost:8000

# Single test file
pytest test_filters.py --base-url=http://localhost:8000
```

### 9.4 With Verbose Timing

```bash
pytest -m performance --base-url=http://localhost:8000 -v --tb=short --durations=10
```

---

## 10. Test Namespaces Required

The target service must have these namespaces configured:

| Namespace | ID Length | Purpose |
|-----------|-----------|---------|
| `test_ns_1` | 5 | Exhaustive uniqueness test (namespace 1) |
| `test_ns_2` | 5 | Exhaustive uniqueness test (namespace 2) |
| `test_perf_ns` | 10 | Performance tests (large pool, not exhausted) |

**Warning**: Running the exhaustive tests will permanently consume ALL IDs in `test_ns_1` and `test_ns_2`. These namespaces must be reset (drop and recreate tables) before re-running.

---

## 11. Test Data Management

### 11.1 Session-Scoped Collection

IDs issued during exhaustive tests are stored in session-scoped pytest fixtures:

```python
@pytest.fixture(scope="session")
def ns1_issued_ids():
    """Populated by EXH-001. List of all IDs issued from test_ns_1, in order."""
    return []
```

This allows later tests (FLT-015, EXH-003, etc.) to reuse the collected data without re-issuing.

### 11.2 Test Reset

To re-run exhaustive tests, the test namespaces must be reset. This can be done by:
1. Restarting the service with the test namespaces in config (tables are re-created if dropped).
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
| Exhaustive (uniqueness & randomness) | 8 | Slow (~minutes) | Consumes all IDs in test_ns_1, test_ns_2 |
| Filters (validation rules) | 18 | Fast (seconds) | None (uses Validate API), except FLT-015 |
| Exhaustion (error handling) | 4 | Fast (seconds) | Requires prior exhaustion |
| Performance (response time) | 4 | Medium (~30s) | Consumes ~200 IDs from test_perf_ns |
| API Contract (OpenAPI, HTTP status, format, errors, version) | 15 | Fast (seconds) | Consumes ~3 IDs |
| **Total** | **49** | | |
