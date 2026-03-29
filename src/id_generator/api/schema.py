"""
Response envelope models and helper functions.

All API responses are wrapped in a standard envelope with id, version,
responsetime, response, and errors fields.
"""

from datetime import datetime, timezone


def _now_iso() -> str:
    """Current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def make_response(response_data: dict) -> dict:
    """Create a successful response envelope.

    Args:
        response_data: The response payload.

    Returns:
        Complete response envelope dict.
    """
    return {
        "id": "openg2p.idgenerator",
        "version": "1.0",
        "responsetime": _now_iso(),
        "response": response_data,
        "errors": [],
    }


def make_error_response(error_code: str, message: str) -> dict:
    """Create an error response envelope.

    Args:
        error_code: The error code (e.g., "IDG-001").
        message: Human-readable error message.

    Returns:
        Complete error response envelope dict.
    """
    return {
        "id": "openg2p.idgenerator",
        "version": "1.0",
        "responsetime": _now_iso(),
        "response": None,
        "errors": [{"errorCode": error_code, "message": message}],
    }
