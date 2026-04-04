"""Backend-neutral JSON helpers for pilot persistence payload columns."""

from __future__ import annotations

import json
from typing import Any


def dumps(payload: Any) -> str:
    """Serialize JSON payloads deterministically for DB storage."""
    return json.dumps(payload, sort_keys=True)


def loads(payload: str) -> Any:
    """Deserialize JSON payloads loaded from DB storage."""
    return json.loads(payload)

