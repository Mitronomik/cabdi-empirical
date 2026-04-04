"""Researcher experiment-run management service."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from uuid import uuid4

from app.participant_api.persistence.sqlite_store import SQLiteStore, dumps, loads
from pilot.config_loader import load_experiment_config

RUN_STATUS_DRAFT = "draft"
RUN_STATUS_ACTIVE = "active"
RUN_STATUS_PAUSED = "paused"
RUN_STATUS_CLOSED = "closed"
RUN_STATUSES = {RUN_STATUS_DRAFT, RUN_STATUS_ACTIVE, RUN_STATUS_PAUSED, RUN_STATUS_CLOSED}
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    RUN_STATUS_DRAFT: {RUN_STATUS_ACTIVE},
    RUN_STATUS_ACTIVE: {RUN_STATUS_PAUSED, RUN_STATUS_CLOSED},
    RUN_STATUS_PAUSED: {RUN_STATUS_ACTIVE, RUN_STATUS_CLOSED},
    RUN_STATUS_CLOSED: set(),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return normalized[:64]

    def _build_unique_public_slug(self, run_name: str, requested_slug: str | None) -> str:
        base_slug = self._slugify(requested_slug or run_name)
        if not base_slug:
            raise ValueError("public_slug must contain at least one alphanumeric character")
        candidate = base_slug
        suffix = 2
        while self.store.fetchone("SELECT run_id FROM researcher_runs WHERE public_slug = ?", (candidate,)) is not None:
            candidate = f"{base_slug}-{suffix}"
            suffix += 1
        return candidate

    def create_run(
        self,
        *,
        run_name: str,
        experiment_id: str,
        task_family: str,
        config: dict[str, Any],
        stimulus_set_ids: list[str],
        notes: str | None,
        public_slug: str | None = None,
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
                "SELECT stimulus_set_id, task_family, validation_status FROM researcher_stimulus_sets WHERE stimulus_set_id = ?",
                (stimulus_set_id,),
            )
            if row is None:
                raise ValueError(f"Unknown stimulus_set_id: {stimulus_set_id}")
            if row["task_family"] != task_family:
                raise ValueError("All selected stimulus sets must match run task_family")
            if row.get("validation_status") not in {"valid", "warning_only"}:
                raise ValueError(f"Stimulus set is not run-compatible: {stimulus_set_id}")

        run_id = f"run_{uuid4().hex[:10]}"
        resolved_public_slug = self._build_unique_public_slug(run_name, public_slug)
        self.store.execute(
            """
            INSERT INTO researcher_runs(
                run_id, run_name, public_slug, status, experiment_id, task_family, config_json,
                stimulus_set_ids_json, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run_name,
                resolved_public_slug,
                RUN_STATUS_DRAFT,
                experiment_id,
                task_family,
                dumps(config),
                dumps(stimulus_set_ids),
                notes,
                _now_iso(),
            ),
        )
        created = self.get_run(run_id)
        return {
            "ok": True,
            "success": True,
            "run_id": created["run_id"],
            "run_name": created["run_name"],
            "public_slug": created["public_slug"],
            "status": created["status"],
            "experiment_id": created["experiment_id"],
            "task_family": created["task_family"],
            "config": created["config"],
            "linked_stimulus_set_ids": created["stimulus_set_ids"],
            "notes": created["notes"],
            "created_at": created["created_at"],
            "validation_errors": [],
        }

    def get_run(self, run_id: str) -> dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM researcher_runs WHERE run_id = ?", (run_id,))
        if row is None:
            raise KeyError("run not found")
        if row.get("status") not in RUN_STATUSES:
            row["status"] = RUN_STATUS_DRAFT
            self.store.execute("UPDATE researcher_runs SET status = ? WHERE run_id = ?", (RUN_STATUS_DRAFT, run_id))
        if not row.get("public_slug"):
            synthesized_slug = self._build_unique_public_slug(row["run_name"], None)
            self.store.execute("UPDATE researcher_runs SET public_slug = ? WHERE run_id = ?", (synthesized_slug, run_id))
            row["public_slug"] = synthesized_slug
        row["config"] = loads(row.pop("config_json"))
        row["stimulus_set_ids"] = loads(row.pop("stimulus_set_ids_json"))
        row["launchable"] = row["status"] == RUN_STATUS_ACTIVE
        row["launchability_reason"] = (
            "run is active and accepts participant sessions"
            if row["status"] == RUN_STATUS_ACTIVE
            else f"run is {row['status']}; activate to accept new participant sessions"
        )
        return row

    def list_runs(self) -> list[dict[str, Any]]:
        rows = self.store.fetchall(
            """
            SELECT run_id, run_name, public_slug, status, experiment_id, task_family, notes, created_at, stimulus_set_ids_json
            FROM researcher_runs
            ORDER BY created_at DESC
            """,
            (),
        )
        for row in rows:
            row["linked_stimulus_set_ids"] = loads(row.pop("stimulus_set_ids_json"))
            row["launchable"] = row["status"] == RUN_STATUS_ACTIVE
            row["launchability_reason"] = (
                "run is active and accepts participant sessions"
                if row["status"] == RUN_STATUS_ACTIVE
                else f"run is {row['status']}; activate to accept new participant sessions"
            )
        return rows

    def transition_run_status(self, run_id: str, target_status: str) -> dict[str, Any]:
        if target_status not in RUN_STATUSES:
            raise ValueError(f"Unsupported run status: {target_status}")
        run = self.get_run(run_id)
        current_status = str(run.get("status", RUN_STATUS_DRAFT))
        if current_status == target_status:
            return self._transition_response(run, validation_errors=[])
        if target_status not in _ALLOWED_TRANSITIONS[current_status]:
            allowed = sorted(_ALLOWED_TRANSITIONS[current_status])
            raise ValueError(
                f"Invalid run status transition: {current_status} -> {target_status}. "
                f"Allowed transitions: {allowed or 'none'}"
            )
        validation_errors = self._validate_launchability(run) if target_status == RUN_STATUS_ACTIVE else []
        if validation_errors:
            raise ValueError(f"Run cannot be activated: {'; '.join(validation_errors)}")

        self.store.execute("UPDATE researcher_runs SET status = ? WHERE run_id = ?", (target_status, run_id))
        updated = self.get_run(run_id)
        return self._transition_response(updated, validation_errors=[])

    def activate_run(self, run_id: str) -> dict[str, Any]:
        return self.transition_run_status(run_id, RUN_STATUS_ACTIVE)

    def pause_run(self, run_id: str) -> dict[str, Any]:
        return self.transition_run_status(run_id, RUN_STATUS_PAUSED)

    def close_run(self, run_id: str) -> dict[str, Any]:
        return self.transition_run_status(run_id, RUN_STATUS_CLOSED)

    def _transition_response(self, run: dict[str, Any], *, validation_errors: list[str]) -> dict[str, Any]:
        return {
            "ok": True,
            "success": True,
            "run_id": run["run_id"],
            "public_slug": run["public_slug"],
            "status": run["status"],
            "task_family": run["task_family"],
            "linked_stimulus_set_ids": run["stimulus_set_ids"],
            "validation_errors": validation_errors,
        }

    def _validate_launchability(self, run: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not str(run.get("experiment_id", "")).strip():
            errors.append("run.experiment_id must be non-empty")
        if not str(run.get("task_family", "")).strip():
            errors.append("run.task_family must be non-empty")

        config = run.get("config")
        if not isinstance(config, dict) or not config:
            errors.append("run.config must be a non-empty object")

        stimulus_set_ids = run.get("stimulus_set_ids")
        if not isinstance(stimulus_set_ids, list) or not stimulus_set_ids:
            errors.append("run must reference at least one stimulus_set_id")
            return errors

        for stimulus_set_id in stimulus_set_ids:
            row = self.store.fetchone(
                """
                SELECT stimulus_set_id, task_family, validation_status, items_json
                FROM researcher_stimulus_sets
                WHERE stimulus_set_id = ?
                """,
                (stimulus_set_id,),
            )
            if row is None:
                errors.append(f"run references missing stimulus_set_id: {stimulus_set_id}")
                continue
            if row["task_family"] != run["task_family"]:
                errors.append(f"stimulus_set_id task_family mismatch: {stimulus_set_id}")
            if row.get("validation_status") not in {"valid", "warning_only"}:
                errors.append(f"stimulus_set_id is not run-compatible: {stimulus_set_id}")
            items = loads(row["items_json"])
            if not isinstance(items, list) or not items:
                errors.append(f"stimulus_set_id has no usable items: {stimulus_set_id}")
        return errors

    def list_run_sessions(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        rows = self.store.fetchall(
            """
            SELECT
                session_id,
                participant_id,
                experiment_id,
                run_id,
                status,
                started_at,
                completed_at,
                last_activity_at,
                current_block_index,
                current_trial_index,
                COALESCE(language, 'en') AS language
            FROM participant_sessions
            WHERE run_id = ?
            ORDER BY started_at
            """,
            (run_id,),
        )
        counts = {
            "created": 0,
            "in_progress": 0,
            "paused": 0,
            "awaiting_final_submit": 0,
            "finalized": 0,
            "abandoned": 0,
        }
        completion_seconds: list[float] = []
        for row in rows:
            status = row["status"]
            if status == "completed":
                status = "finalized"
                row["status"] = "finalized"
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
            "public_slug": run["public_slug"],
            "run_status": run["status"],
            "counts": counts,
            "mean_completion_seconds": mean_completion_seconds,
            "sessions": rows,
        }

    def get_run_builder_defaults(self) -> dict[str, Any]:
        experiment = load_experiment_config("pilot/configs/default_experiment.yaml")
        return {
            "experiment_id": experiment.experiment_id,
            "task_family": experiment.task_family,
            "config_preset_id": "default_experiment",
            "config_preset_options": [
                {
                    "preset_id": "default_experiment",
                    "label": "Default experiment config",
                    "config": {
                        "n_blocks": experiment.n_blocks,
                        "trials_per_block": experiment.trials_per_block,
                        "budget_matching_mode": experiment.budget_matching_mode,
                    },
                }
            ],
        }
