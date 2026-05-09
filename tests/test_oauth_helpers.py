"""Tests for pure OAuth helpers used by the config flow.

These functions live in `_oauth_helpers.py` so they can be tested without
pulling in Home Assistant's test plugin (which is a heavy dependency for
just three small functions).
"""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

# Load the helpers module directly so the test doesn't trigger the package
# __init__.py (which imports `homeassistant`).
_HELPERS_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "kohler_anthem"
    / "_oauth_helpers.py"
)
_spec = importlib.util.spec_from_file_location("_oauth_helpers", _HELPERS_PATH)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
decode_jwt_oid = _module.decode_jwt_oid
extract_code_and_state = _module.extract_code_and_state
username_from_token = _module.username_from_token


def _fake_jwt(claims: dict) -> str:
    """Build a JWT with the given payload claims (signature is junk — we don't verify)."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256","typ":"JWT"}').rstrip(b"=").decode()
    payload = (
        base64.urlsafe_b64encode(json.dumps(claims).encode("utf-8")).rstrip(b"=").decode()
    )
    return f"{header}.{payload}.signature"


# ---------------------------------------------------------------------------
# decode_jwt_oid
# ---------------------------------------------------------------------------


class TestDecodeJwtOid:
    def test_returns_oid_when_present(self) -> None:
        token = _fake_jwt({"oid": "tenant-123", "sub": "subject-456"})
        assert decode_jwt_oid(token) == "tenant-123"

    def test_falls_back_to_sub_when_oid_missing(self) -> None:
        token = _fake_jwt({"sub": "subject-456"})
        assert decode_jwt_oid(token) == "subject-456"

    def test_returns_none_for_malformed_token(self) -> None:
        assert decode_jwt_oid("not.a.real-jwt-payload") is None
        assert decode_jwt_oid("nodots") is None
        assert decode_jwt_oid("") is None

    def test_returns_none_when_oid_is_not_a_string(self) -> None:
        token = _fake_jwt({"oid": 12345, "sub": ["a", "b"]})
        assert decode_jwt_oid(token) is None


# ---------------------------------------------------------------------------
# username_from_token
# ---------------------------------------------------------------------------


class TestUsernameFromToken:
    def test_returns_first_email_when_present(self) -> None:
        token = _fake_jwt({"emails": ["user@example.com"]})
        assert username_from_token(token) == "user@example.com"

    def test_falls_back_to_name(self) -> None:
        token = _fake_jwt({"name": "Alice"})
        assert username_from_token(token) == "Alice"

    def test_returns_none_when_neither_present(self) -> None:
        token = _fake_jwt({"oid": "x"})
        assert username_from_token(token) is None

    def test_returns_none_for_malformed(self) -> None:
        assert username_from_token("garbage") is None


# ---------------------------------------------------------------------------
# extract_code_and_state
# ---------------------------------------------------------------------------


class TestExtractCodeAndState:
    def test_parses_loopback_url(self) -> None:
        url = "http://127.0.0.1:8765/oauth/callback?code=abc&state=xyz"
        code, state, error = extract_code_and_state(url)
        assert code == "abc"
        assert state == "xyz"
        assert error is None

    def test_parses_custom_scheme_url(self) -> None:
        """The mobile app's redirect scheme parses correctly."""
        url = "msauth.com.kohler.hermoth://auth?code=abc&state=xyz"
        code, state, error = extract_code_and_state(url)
        assert code == "abc"
        assert state == "xyz"
        assert error is None

    def test_returns_error_when_b2c_returned_error(self) -> None:
        url = (
            "msauth.com.kohler.hermoth://auth?error=access_denied"
            "&error_description=user%20cancelled"
        )
        code, state, error = extract_code_and_state(url)
        assert code is None
        assert state is None
        assert "user cancelled" in (error or "")

    def test_returns_error_when_code_missing(self) -> None:
        url = "http://127.0.0.1:8765/oauth/callback?state=xyz"
        code, state, error = extract_code_and_state(url)
        assert code is None
        assert state is None
        assert error is not None

    def test_returns_error_when_state_missing(self) -> None:
        url = "http://127.0.0.1:8765/oauth/callback?code=abc"
        code, state, error = extract_code_and_state(url)
        assert code is None
        assert state is None
        assert error is not None
