"""Shared pilot persistence protocol used by participant/researcher services."""

from __future__ import annotations

from typing import Any, Protocol


class PilotStore(Protocol):
    def init_db(self) -> None: ...

    def fetchone(self, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None: ...

    def fetchall(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]: ...

    def execute(self, query: str, params: tuple[Any, ...]) -> None: ...

    def executemany(self, query: str, params: list[tuple[Any, ...]]) -> None: ...
