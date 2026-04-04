from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException, Request

from app.researcher_api.services.auth_service import AuthenticatedUser

SESSION_COOKIE_NAME = "researcher_session"
SESSION_TTL_SECONDS = 60 * 60 * 12


def _sign_payload(payload_json: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_json.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def _encode_payload(data: dict[str, Any], secret: str) -> str:
    payload_json = json.dumps(data, separators=(",", ":"), sort_keys=True)
    signature = _sign_payload(payload_json, secret)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("ascii")
    return f"{payload_b64}.{signature}"


def _decode_payload(token: str, secret: str) -> dict[str, Any] | None:
    try:
        payload_b64, signature = token.split(".", 1)
        payload_json = base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None

    expected_signature = _sign_payload(payload_json, secret)
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        data = json.loads(payload_json)
        expires_at = int(data.get("exp", 0))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if expires_at <= int(time.time()):
        return None
    return data


def issue_session_token(user: AuthenticatedUser, secret: str) -> str:
    now = int(time.time())
    return _encode_payload(
        {"sub": user.user_id, "username": user.username, "is_admin": user.is_admin, "iat": now, "exp": now + SESSION_TTL_SECONDS},
        secret,
    )


def require_researcher_auth(request: Request) -> AuthenticatedUser:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Researcher authentication required")

    payload = _decode_payload(token, request.app.state.researcher_session_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired researcher session")

    user = request.app.state.auth_service.get_user(str(payload.get("sub", "")))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired researcher session")
    return user
