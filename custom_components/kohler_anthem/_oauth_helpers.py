"""Pure helpers for the OAuth config flow — no Home Assistant imports.

Lives in its own module so it can be unit-tested without the HA test harness.
"""

from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, urlparse


def decode_jwt_oid(access_token: str) -> str | None:
    """Pull the user's tenant id from the JWT (oid claim, falling back to sub).

    Returns None on any decode error — callers should treat that as missing.
    """
    parts = access_token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    payload += "=" * ((4 - len(payload) % 4) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    oid = claims.get("oid") or claims.get("sub")
    return oid if isinstance(oid, str) else None


def username_from_token(access_token: str) -> str | None:
    """Best-effort: pull a human-readable identifier from the JWT.

    B2C tokens carry ``emails`` (list) and ``name``; either is fine for the
    entry title. Falls back to None so callers can use the tenant id.
    """
    parts = access_token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    payload += "=" * ((4 - len(payload) % 4) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    emails = claims.get("emails")
    if isinstance(emails, list) and emails and isinstance(emails[0], str):
        return emails[0]
    name = claims.get("name")
    return name if isinstance(name, str) else None


def extract_code_and_state(redirect_url: str) -> tuple[str | None, str | None, str | None]:
    """Parse the URL the user pasted back from their browser.

    Returns ``(code, state, error)``. Either ``code+state`` is set, or
    ``error`` is. Custom redirect schemes (``msauth.com.kohler.hermoth://``)
    parse fine via ``urllib.parse``.
    """
    parsed = urlparse(redirect_url)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    if "error" in params:
        description = params.get("error_description") or params["error"]
        return None, None, description
    code = params.get("code")
    state = params.get("state")
    if not code or not state:
        return None, None, "redirect URL did not contain code+state"
    return code, state, None
