"""
Category 5: API Contract Tests (API-001 through API-015)

Verify OpenAPI compliance, HTTP status codes, response envelope structure,
error codes, and edge cases. These run first (Phase 1) to confirm the
service is up and API format is correct before heavier tests.
"""

import re

import pytest


pytestmark = [
    pytest.mark.api_contract,
    pytest.mark.order(1),
    pytest.mark.asyncio(loop_scope="session"),
]


# -------------------------------------------------------------------------
# API-001: Issue ID response envelope
# -------------------------------------------------------------------------
class TestAPI001:
    """POST Issue ID returns correct response envelope."""

    async def test_issue_response_envelope(
        self, client, id_type_1, issue_id
    ):
        resp = await issue_id(client, id_type_1)

        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")

        body = resp.json()
        assert "id" in body
        assert "version" in body
        assert "responsetime" in body
        assert "response" in body
        assert "errors" in body

        # responsetime should be a valid ISO 8601 string
        assert re.match(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", body["responsetime"]
        )

        # response.id should be a string of digits
        assert body["response"] is not None
        assert body["response"]["id"].isdigit()

        # errors should be an empty list on success
        assert body["errors"] == []


# -------------------------------------------------------------------------
# API-002: Validate ID response envelope
# -------------------------------------------------------------------------
class TestAPI002:
    """GET Validate ID returns correct response envelope."""

    async def test_validate_response_envelope(
        self, client, id_type_1, issue_id, validate_id
    ):
        # First issue an ID to validate
        issue_resp = await issue_id(client, id_type_1)
        issued_id = issue_resp.json()["response"]["id"]

        resp = await validate_id(client, id_type_1, issued_id)

        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")

        body = resp.json()
        assert "id" in body
        assert "version" in body
        assert "responsetime" in body
        assert "response" in body
        assert "errors" in body

        # Validate response has id and valid fields
        assert "id" in body["response"]
        assert "valid" in body["response"]
        assert isinstance(body["response"]["valid"], bool)


# -------------------------------------------------------------------------
# API-003: Unknown ID type returns 404 with IDG-003
# -------------------------------------------------------------------------
class TestAPI003:
    """POST to unknown ID type returns HTTP 404 with IDG-003."""

    async def test_unknown_id_type_returns_404(self, client, issue_id):
        resp = await issue_id(client, "nonexistent_id_type_xyz")

        assert resp.status_code == 404

        body = resp.json()
        assert body["response"] is None
        assert len(body["errors"]) > 0
        assert body["errors"][0]["errorCode"] == "IDG-003"


# -------------------------------------------------------------------------
# API-004: Validate with unknown ID type returns 404
# -------------------------------------------------------------------------
class TestAPI004:
    """GET Validate with unknown ID type returns HTTP 404 with IDG-003."""

    async def test_validate_unknown_id_type_returns_404(
        self, client, validate_id
    ):
        resp = await validate_id(
            client, "nonexistent_id_type_xyz", "12345"
        )

        assert resp.status_code == 404

        body = resp.json()
        assert len(body["errors"]) > 0
        assert body["errors"][0]["errorCode"] == "IDG-003"


# -------------------------------------------------------------------------
# API-005: Health endpoint returns healthy
# -------------------------------------------------------------------------
class TestAPI005:
    """GET Health returns HTTP 200 when service is healthy."""

    async def test_health_endpoint_returns_healthy(
        self, client, health_check
    ):
        resp = await health_check(client)
        assert resp.status_code == 200


# -------------------------------------------------------------------------
# API-006: Issued ID is numeric
# -------------------------------------------------------------------------
class TestAPI006:
    """Issued ID contains only digits."""

    async def test_issued_id_is_numeric(self, client, id_type_1, issue_id):
        resp = await issue_id(client, id_type_1)
        assert resp.status_code == 200

        issued_id = resp.json()["response"]["id"]
        assert issued_id.isdigit(), f"ID '{issued_id}' is not purely numeric"


# -------------------------------------------------------------------------
# API-007: Issued ID has correct length
# -------------------------------------------------------------------------
class TestAPI007:
    """Issued ID length matches ID type configuration."""

    async def test_issued_id_correct_length(
        self, client, id_type_1, id_type_1_length, issue_id
    ):
        resp = await issue_id(client, id_type_1)
        assert resp.status_code == 200

        issued_id = resp.json()["response"]["id"]
        assert len(issued_id) == id_type_1_length, (
            f"Expected length {id_type_1_length}, got {len(issued_id)} "
            f"for ID '{issued_id}'"
        )


# -------------------------------------------------------------------------
# API-008: Issued ID passes validation
# -------------------------------------------------------------------------
class TestAPI008:
    """An issued ID should pass the service's own validation endpoint."""

    async def test_issued_id_passes_validation(
        self, client, id_type_1, issue_id, validate_id
    ):
        issue_resp = await issue_id(client, id_type_1)
        assert issue_resp.status_code == 200
        issued_id = issue_resp.json()["response"]["id"]

        val_resp = await validate_id(client, id_type_1, issued_id)
        assert val_resp.status_code == 200

        body = val_resp.json()
        assert body["response"]["valid"] is True


# -------------------------------------------------------------------------
# API-009: Version endpoint
# -------------------------------------------------------------------------
class TestAPI009:
    """GET Version returns service_version, build_time, git_commit."""

    async def test_version_endpoint(self, client):
        resp = await client.get("/v1/idgenerator/version")

        assert resp.status_code == 200

        body = resp.json()
        version_data = body["response"]
        assert "service_version" in version_data
        assert "build_time" in version_data
        assert "git_commit" in version_data

        # service_version should look like semver (at least X.Y.Z)
        assert re.match(r"\d+\.\d+\.\d+", version_data["service_version"])


# -------------------------------------------------------------------------
# API-010: Version response envelope
# -------------------------------------------------------------------------
class TestAPI010:
    """Version response follows the standard response envelope."""

    async def test_version_response_envelope(self, client):
        resp = await client.get("/v1/idgenerator/version")
        assert resp.status_code == 200

        body = resp.json()
        assert "id" in body
        assert "version" in body
        assert "responsetime" in body
        assert "response" in body
        assert "errors" in body
        assert body["errors"] == []


# -------------------------------------------------------------------------
# API-011: GET on Issue endpoint returns 405 Method Not Allowed
# -------------------------------------------------------------------------
class TestAPI011:
    """GET (not POST) to Issue ID endpoint returns HTTP 405."""

    async def test_issue_id_get_not_allowed(self, client, id_type_1):
        resp = await client.get(f"/v1/idgenerator/{id_type_1}/id")
        assert resp.status_code == 405


# -------------------------------------------------------------------------
# API-012: Invalid ID type format returns 422
# -------------------------------------------------------------------------
class TestAPI012:
    """POST with invalid ID type format returns HTTP 422."""

    @pytest.mark.parametrize(
        "bad_id_type",
        ["123invalid", "UPPER", "ns with spaces"],
        ids=["starts-with-digit", "uppercase", "contains-space"],
    )
    async def test_invalid_id_type_format_returns_422(
        self, client, bad_id_type
    ):
        resp = await client.post(f"/v1/idgenerator/{bad_id_type}/id")
        assert resp.status_code == 422


# -------------------------------------------------------------------------
# API-013: Invalid ID format in validate returns 422
# -------------------------------------------------------------------------
class TestAPI013:
    """GET Validate with non-numeric ID returns HTTP 422."""

    @pytest.mark.parametrize(
        "bad_id",
        ["abc", "12.34", "12 34"],
        ids=["alphabetic", "decimal", "spaces"],
    )
    async def test_invalid_id_format_returns_422(
        self, client, id_type_1, bad_id
    ):
        resp = await client.get(
            f"/v1/idgenerator/{id_type_1}/id/validate/{bad_id}"
        )
        assert resp.status_code == 422


# -------------------------------------------------------------------------
# API-014: OpenAPI spec is available
# -------------------------------------------------------------------------
class TestAPI014:
    """GET /openapi.json returns a valid OpenAPI 3.x spec."""

    async def test_openapi_spec_available(self, client):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200

        body = resp.json()
        assert "openapi" in body
        assert body["openapi"].startswith("3.")


# -------------------------------------------------------------------------
# API-015: All endpoints return Content-Type: application/json
# -------------------------------------------------------------------------
class TestAPI015:
    """All endpoints return Content-Type: application/json."""

    async def test_content_type_json(
        self, client, id_type_1, issue_id, validate_id, health_check
    ):
        # Issue ID
        resp = await issue_id(client, id_type_1)
        assert "application/json" in resp.headers.get("content-type", ""), (
            "Issue ID missing application/json content-type"
        )

        issued_id = resp.json()["response"]["id"]

        # Validate ID
        resp = await validate_id(client, id_type_1, issued_id)
        assert "application/json" in resp.headers.get("content-type", ""), (
            "Validate ID missing application/json content-type"
        )

        # Health
        resp = await health_check(client)
        assert "application/json" in resp.headers.get("content-type", ""), (
            "Health missing application/json content-type"
        )

        # Version
        resp = await client.get("/v1/idgenerator/version")
        assert "application/json" in resp.headers.get("content-type", ""), (
            "Version missing application/json content-type"
        )
