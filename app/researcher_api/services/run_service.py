"""Researcher experiment-run management service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.participant_api.persistence.sqlite_store import SQLiteStore, dumps, loads


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def create_run(
        self,
        *,
        run_name: str,
        experiment_id: str,
        task_family: str,
        config: dict[str, Any],
        stimulus_set_ids: list[str],
        notes: str | None,
    ) -> dict[str, Any]:
        if not run_name.strip():
            raise ValueError("run_name must be non-empty")
        if not experiment_id.strip():
            raise ValueError("experiment_id must be non-empty")
        if not task_family.strip():
            raise ValueError("task_family must be non-empty")
        if not stimulus_set_ids:
            raise ValueError("at least one stimulus_set_id is required")

        for stimulus_set_id in stimulus_set_ids:
            row = self.store.fetchone(
                "SELECT stimulus_set_id, task_family FROM researcher_stimulus_sets WHERE stimulus_set_id = ?",
                (stimulus_set_id,),
            )
            if row is None:
                raise ValueError(f"Unknown stimulus_set_id: {stimulus_set_id}")
            if row["task_family"] != task_family:
                raise ValueError("All selected stimulus sets must match run task_family")

        run_id = f"run_{uuid4().hex[:10]}"
        self.store.execute(
            """
            INSERT INTO researcher_runs(
                run_id, run_name, experiment_id, task_family, config_json,
                stimulus_set_ids_json, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run_name,
                experiment_id,
                task_family,
                dumps(config),
                dumps(stimulus_set_ids),
                notes,
                _now_iso(),
            ),
        )
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM researcher_runs WHERE run_id = ?", (run_id,))
        if row is None:
            raise KeyError("run not found")
        row["config"] = loads(row.pop("config_json"))
        row["stimulus_set_ids"] = loads(row.pop("stimulus_set_ids_json"))
        return row

    def list_run_sessions(self, run_id: str) -> dict[str, Any]:
        self.get_run(run_id)
        rows = self.store.fetchall(
            "SELECT session_id, participant_id, experiment_id, run_id, status, started_at, completed_at, COALESCE(language, 'en') AS language FROM participant_sessions WHERE run_id = ? ORDER BY started_at",
            (run_id,),
        )
        counts = {"created": 0, "in_progress": 0, "completed": 0, "abandoned": 0}
        completion_seconds: list[float] = []
        for row in rows:
            status = row["status"]
            if status in counts:
                counts[status] += 1
            else:
                counts["abandoned"] += 1
            if row["started_at"] and row["completed_at"]:
                started = datetime.fromisoformat(row["started_at"])
                completed = datetime.fromisoformat(row["completed_at"])
                completion_seconds.append((completed - started).total_seconds())

        mean_completion_seconds = sum(completion_seconds) / len(completion_seconds) if completion_seconds else None
        return {
            "run_id": run_id,
            "counts": counts,
            "mean_completion_seconds": mean_completion_seconds,
            "sessions": rows,
        }
