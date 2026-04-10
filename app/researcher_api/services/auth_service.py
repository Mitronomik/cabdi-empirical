from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.participant_api.persistence.store_protocol import PilotStore


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    username: str
    is_admin: bool


class AuthService:
    """Minimal researcher/admin identity and password auth service."""

    HASH_ITERATIONS = 210_000
    LOCAL_DEFAULT_BOOTSTRAP_PASSWORD = "admin1234"
    WEAK_BOOTSTRAP_PASSWORDS = {
        "admin",
        "admin123",
        "admin1234",
        "changeme",
        "change-me",
        "password",
        "password123",
        "researcher",
        "strong-pass",
        "letmein",
        "qwerty123",
    }

    def __init__(self, store: PilotStore) -> None:
        self._store = store

    def bootstrap_initial_user(self) -> None:
        row = self._store.fetchone("SELECT COUNT(*) AS n FROM researcher_users", ())
        if int((row or {}).get("n", 0)) > 0:
            return

        username = os.getenv("PILOT_RESEARCHER_USERNAME", "admin")
        password = os.getenv("PILOT_RESEARCHER_PASSWORD")
        env_mode = os.getenv("PILOT_ENV", "local").strip().lower()

        if not password:
            if env_mode in {"prod", "production", "staging"}:
                raise RuntimeError(
                    "Researcher auth bootstrap requires PILOT_RESEARCHER_PASSWORD in production-like mode."
                )
            password = self.LOCAL_DEFAULT_BOOTSTRAP_PASSWORD
        elif env_mode in {"prod", "production", "staging"} and self._is_weak_bootstrap_password(
            password
        ):
            raise RuntimeError(
                "PILOT_RESEARCHER_PASSWORD is too weak for production-like mode. "
                "Set a non-default bootstrap password with at least 12 characters and no placeholder text."
            )

        self._store.execute(
            """
            INSERT INTO researcher_users(user_id, username, password_hash, is_admin, is_active, created_at)
            VALUES (?, ?, ?, 1, 1, ?)
            """,
            (
                f"usr_{uuid4().hex[:12]}",
                username,
                self.hash_password(password),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def _is_weak_bootstrap_password(self, password: str) -> bool:
        normalized = password.strip().lower()
        if len(password) < 12:
            return True
        if normalized in self.WEAK_BOOTSTRAP_PASSWORDS:
            return True
        weak_markers = ("change", "changeme", "password", "admin", "default", "example", "test")
        return any(marker in normalized for marker in weak_markers)

    def authenticate(self, username: str, password: str) -> AuthenticatedUser | None:
        row = self._store.fetchone(
            """
            SELECT user_id, username, password_hash, is_admin, is_active
            FROM researcher_users
            WHERE username = ?
            """,
            (username,),
        )
        if not row or int(row.get("is_active", 0)) != 1:
            return None
        if not self.verify_password(password=password, password_hash=str(row["password_hash"])):
            return None
        return AuthenticatedUser(
            user_id=str(row["user_id"]),
            username=str(row["username"]),
            is_admin=bool(int(row.get("is_admin", 0))),
        )

    def get_user(self, user_id: str) -> AuthenticatedUser | None:
        row = self._store.fetchone(
            "SELECT user_id, username, is_admin, is_active FROM researcher_users WHERE user_id = ?",
            (user_id,),
        )
        if not row or int(row.get("is_active", 0)) != 1:
            return None
        return AuthenticatedUser(
            user_id=str(row["user_id"]),
            username=str(row["username"]),
            is_admin=bool(int(row.get("is_admin", 0))),
        )

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self.HASH_ITERATIONS)
        salt_b64 = base64.b64encode(salt).decode("ascii")
        digest_b64 = base64.b64encode(digest).decode("ascii")
        return f"pbkdf2_sha256${self.HASH_ITERATIONS}${salt_b64}${digest_b64}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            algorithm, iterations_str, salt_b64, expected_digest_b64 = password_hash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            iterations = int(iterations_str)
            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected_digest = base64.b64decode(expected_digest_b64.encode("ascii"))
        except (ValueError, TypeError):
            return False

        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(digest, expected_digest)

    def make_session_payload(self, user: AuthenticatedUser) -> dict[str, Any]:
        return {
            "user_id": user.user_id,
            "username": user.username,
            "is_admin": user.is_admin,
            "issued_at": datetime.now(timezone.utc).isoformat(),
        }
