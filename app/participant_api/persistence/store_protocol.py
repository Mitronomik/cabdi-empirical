"""Shared pilot persistence protocol used by participant/researcher services."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol


class PilotStore(Protocol):
    """Backend-neutral contract used by pilot services and persistence tooling.

    Service-layer code should rely on query methods only.
    Infrastructure utilities (for example backup/restore) may additionally rely on
    `schema_version`, `placeholders`, and `transaction`.
    """

    @property
    def schema_version(self) -> int: ...

    def init_db(self) -> None: ...

    def fetchone(self, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None: ...

    def fetchall(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]: ...

    def execute(self, query: str, params: tuple[Any, ...]) -> None: ...

    def executemany(self, query: str, params: list[tuple[Any, ...]]) -> None: ...

    def placeholders(self, n: int) -> str: ...

    def transaction(self) -> AbstractContextManager[Any]: ...
