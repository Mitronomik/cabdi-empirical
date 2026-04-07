"""Researcher experiment-run management service."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from uuid import uuid4

from app.participant_api.persistence.json_codec import dumps, loads
from app.participant_api.persistence.store_protocol import PilotStore
from app.participant_api.services.run_config_service import materialize_run_config_for_storage, resolve_execution_config_from_run
from pilot.config_loader import load_experiment_config

RUN_STATUS_DRAFT = "draft"
RUN_STATUS_ACTIVE = "active"
RUN_STATUS_PAUSED = "paused"
RUN_STATUS_CLOSED = "closed"
RUN_STATUSES = {RUN_STATUS_DRAFT, RUN_STATUS_ACTIVE, RUN_STATUS_PAUSED, RUN_STATUS_CLOSED}
AGGREGATION_MODE_SINGLE = "single"
AGGREGATION_MODE_MULTI = "multi"
_ALLOWED_AGGREGATION_MODES = {AGGREGATION_MODE_SINGLE, AGGREGATION_MODE_MULTI}
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    RUN_STATUS_DRAFT: {RUN_STATUS_ACTIVE},
    RUN_STATUS_ACTIVE: {RUN_STATUS_PAUSED, RUN_STATUS_CLOSED},
    RUN_STATUS_PAUSED: {RUN_STATUS_ACTIVE, RUN_STATUS_CLOSED},
    RUN_STATUS_CLOSED: set(),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_expected_trial_count(*, practice_item_count: int, main_item_count: int) -> int:
    return int(practice_item_count) + int(main_item_count)


class RunService:
    def __init__(self, store: PilotStore, *, participant_base_url: str = "http://localhost:5173") -> None:
        self.store = store
        self.participant_base_url = participant_base_url.rstrip("/")

    def _invite_url(self, public_slug: str) -> str:
        return f"{self.participant_base_url}/join/{public_slug}"

    @staticmethod
    def _launchability_state(launchable: bool) -> str:
        return "launchable" if launchable else "not_launchable"

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
        aggregation_mode: str = AGGREGATION_MODE_SINGLE,
        practice_stimulus_set_id: str | None = None,
        public_slug: str | None = None,
    ) -> dict[str, Any]:
        if not run_name.strip():
            raise ValueError("run_name must be non-empty")
        if not experiment_id.strip():
            raise ValueError("experiment_id must be non-empty")
        if not task_family.strip():
            raise ValueError("task_family must be non-empty")
        if aggregation_mode not in _ALLOWED_AGGREGATION_MODES:
            raise ValueError(f"aggregation_mode must be one of: {sorted(_ALLOWED_AGGREGATION_MODES)}")
        main_stimulus_set_ids = [set_id for set_id in stimulus_set_ids if str(set_id).strip()]
        if not main_stimulus_set_ids:
            raise ValueError("at least one main stimulus_set_id is required")
        if aggregation_mode == AGGREGATION_MODE_SINGLE and len(main_stimulus_set_ids) != 1:
            raise ValueError("single aggregation_mode requires exactly one main stimulus_set_id")
        if aggregation_mode == AGGREGATION_MODE_MULTI and len(main_stimulus_set_ids) < 2:
            raise ValueError("multi aggregation_mode requires at least two main stimulus_set_ids")

        default_experiment = load_experiment_config("pilot/configs/default_experiment.yaml")
        resolved_config = materialize_run_config_for_storage(
            run_config=config,
            default_experiment=default_experiment,
            experiment_id=experiment_id,
            task_family=task_family,
        )

        self._validate_stimulus_sets_for_run(
            task_family=task_family,
            main_stimulus_set_ids=main_stimulus_set_ids,
            practice_stimulus_set_id=practice_stimulus_set_id,
        )

        run_summary = self._compute_run_summary(
            main_stimulus_set_ids=main_stimulus_set_ids,
            practice_stimulus_set_id=practice_stimulus_set_id,
            aggregation_mode=aggregation_mode,
        )

        for stimulus_set_id in main_stimulus_set_ids:
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
                stimulus_set_ids_json, notes, created_at, aggregation_mode, practice_stimulus_set_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run_name,
                resolved_public_slug,
                RUN_STATUS_DRAFT,
                experiment_id,
                task_family,
                dumps(resolved_config),
                dumps(main_stimulus_set_ids),
                notes,
                _now_iso(),
                1 if aggregation_mode == AGGREGATION_MODE_MULTI else 0,
                practice_stimulus_set_id,
            ),
        )
        created = self.get_run(run_id)
        return {
            "ok": True,
            "success": True,
            "run_id": created["run_id"],
            "run_name": created["run_name"],
            "public_slug": created["public_slug"],
            "invite_url": created["invite_url"],
            "status": created["status"],
            "run_status": created["status"],
            "experiment_id": created["experiment_id"],
            "task_family": created["task_family"],
            "config": created["config"],
            "linked_stimulus_set_ids": created["stimulus_set_ids"],
            "run_summary": created["run_summary"],
            "aggregation_mode": created["aggregation_mode"],
            "practice_stimulus_set_id": created["practice_stimulus_set_id"],
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
        row["aggregation_mode"] = AGGREGATION_MODE_MULTI if int(row.get("aggregation_mode") or 0) == 1 else AGGREGATION_MODE_SINGLE
        row["practice_stimulus_set_id"] = row.get("practice_stimulus_set_id")
        row["run_summary"] = self._compute_run_summary(
            main_stimulus_set_ids=row["stimulus_set_ids"],
            practice_stimulus_set_id=row["practice_stimulus_set_id"],
            aggregation_mode=row["aggregation_mode"],
        )
        row["launchable"] = row["status"] == RUN_STATUS_ACTIVE
        row["launchability_state"] = self._launchability_state(row["launchable"])
        row["launchability_reason"] = (
            "run is active and accepts participant sessions"
            if row["status"] == RUN_STATUS_ACTIVE
            else f"run is {row['status']}; activate to accept new participant sessions"
        )
        row["run_status"] = row["status"]
        row["invite_url"] = self._invite_url(str(row["public_slug"]))
        return row

    def list_runs(self) -> list[dict[str, Any]]:
        rows = self.store.fetchall(
            """
            SELECT run_id, run_name, public_slug, status, experiment_id, task_family, notes, created_at, stimulus_set_ids_json
                   , aggregation_mode, practice_stimulus_set_id
            FROM researcher_runs
            ORDER BY created_at DESC
            """,
            (),
        )
        for row in rows:
            row["linked_stimulus_set_ids"] = loads(row.pop("stimulus_set_ids_json"))
            aggregation_mode = AGGREGATION_MODE_MULTI if int(row.get("aggregation_mode") or 0) == 1 else AGGREGATION_MODE_SINGLE
            row["aggregation_mode"] = aggregation_mode
            row["practice_stimulus_set_id"] = row.get("practice_stimulus_set_id")
            row["run_summary"] = self._compute_run_summary(
                main_stimulus_set_ids=row["linked_stimulus_set_ids"],
                practice_stimulus_set_id=row["practice_stimulus_set_id"],
                aggregation_mode=aggregation_mode,
            )
            row["launchable"] = row["status"] == RUN_STATUS_ACTIVE
            row["launchability_state"] = self._launchability_state(row["launchable"])
            row["launchability_reason"] = (
                "run is active and accepts participant sessions"
                if row["status"] == RUN_STATUS_ACTIVE
                else f"run is {row['status']}; activate to accept new participant sessions"
            )
            row["run_status"] = row["status"]
            row["invite_url"] = self._invite_url(str(row["public_slug"]))
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
            "invite_url": run["invite_url"],
            "status": run["status"],
            "run_status": run["status"],
            "launchable": run["launchable"],
            "launchability_state": run["launchability_state"],
            "launchability_reason": run["launchability_reason"],
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
        else:
            try:
                resolve_execution_config_from_run(
                    run_config=config,
                    run_experiment_id=str(run.get("experiment_id", "")),
                    run_task_family=str(run.get("task_family", "")),
                )
            except ValueError as exc:
                errors.append(str(exc))

        stimulus_set_ids = run.get("stimulus_set_ids")
        if not isinstance(stimulus_set_ids, list) or not stimulus_set_ids:
            errors.append("run must reference at least one stimulus_set_id")
            return errors
        aggregation_mode = str(run.get("aggregation_mode") or AGGREGATION_MODE_SINGLE)
        if aggregation_mode not in _ALLOWED_AGGREGATION_MODES:
            errors.append("run has invalid aggregation_mode")
        if aggregation_mode == AGGREGATION_MODE_SINGLE and len(stimulus_set_ids) != 1:
            errors.append("single-set run cannot include more than one main stimulus set")
        if aggregation_mode == AGGREGATION_MODE_MULTI and len(stimulus_set_ids) < 2:
            errors.append("multi-set run requires at least two main stimulus sets")

        run_summary = run.get("run_summary")
        if not isinstance(run_summary, dict):
            errors.append("run summary missing")
        else:
            expected_total = int(run_summary.get("expected_trial_count", 0))
            if expected_total <= 0:
                errors.append("run summary expected_trial_count must be positive")

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
                created_at,
                started_at,
                completed_at,
                last_activity_at,
                current_block_index,
                current_trial_index,
                COALESCE(language, 'en') AS language
            FROM participant_sessions
            WHERE run_id = ?
            ORDER BY created_at
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
        execution_config = experiment.to_dict()
        return {
            "experiment_id": experiment.experiment_id,
            "task_family": experiment.task_family,
            "config_preset_id": "default_experiment",
            "config_preset_options": [
                {
                    "preset_id": "default_experiment",
                    "label": "Default experiment config",
                    "config": {
                        "execution": execution_config,
                        "n_blocks": experiment.n_blocks,
                        "trials_per_block": experiment.trials_per_block,
                        "budget_matching_mode": experiment.budget_matching_mode,
                    },
                }
            ],
            "aggregation_mode_default": AGGREGATION_MODE_SINGLE,
            "aggregation_mode_options": [AGGREGATION_MODE_SINGLE, AGGREGATION_MODE_MULTI],
        }

    def _validate_stimulus_sets_for_run(
        self,
        *,
        task_family: str,
        main_stimulus_set_ids: list[str],
        practice_stimulus_set_id: str | None,
    ) -> None:
        all_set_ids = list(main_stimulus_set_ids)
        if practice_stimulus_set_id:
            all_set_ids.append(practice_stimulus_set_id)

        payload_versions: set[str] = set()
        for stimulus_set_id in all_set_ids:
            row = self.store.fetchone(
                """
                SELECT stimulus_set_id, task_family, validation_status, payload_schema_version
                FROM researcher_stimulus_sets
                WHERE stimulus_set_id = ?
                """,
                (stimulus_set_id,),
            )
            if row is None:
                raise ValueError(f"Unknown stimulus_set_id: {stimulus_set_id}")
            if row["task_family"] != task_family:
                raise ValueError("All selected stimulus sets must match run task_family")
            if row.get("validation_status") not in {"valid", "warning_only"}:
                raise ValueError(f"Stimulus set is not run-compatible: {stimulus_set_id}")
            payload_versions.add(str(row.get("payload_schema_version") or "stimulus_payload.v1"))
        if len(payload_versions) > 1:
            raise ValueError("Selected stimulus sets have incompatible payload_schema_version values")

    def _compute_run_summary(
        self,
        *,
        main_stimulus_set_ids: list[str],
        practice_stimulus_set_id: str | None,
        aggregation_mode: str,
    ) -> dict[str, Any]:
        banks: list[dict[str, Any]] = []
        main_item_count = 0
        for stimulus_set_id in main_stimulus_set_ids:
            row = self.store.fetchone(
                "SELECT stimulus_set_id, name, n_items FROM researcher_stimulus_sets WHERE stimulus_set_id = ?",
                (stimulus_set_id,),
            )
            if row is None:
                continue
            n_items = int(row.get("n_items") or 0)
            main_item_count += n_items
            banks.append(
                {
                    "stimulus_set_id": row["stimulus_set_id"],
                    "name": row["name"],
                    "n_items": n_items,
                    "role": "main",
                }
            )
        practice_bank: dict[str, Any] | None = None
        if practice_stimulus_set_id:
            row = self.store.fetchone(
                "SELECT stimulus_set_id, name, n_items FROM researcher_stimulus_sets WHERE stimulus_set_id = ?",
                (practice_stimulus_set_id,),
            )
            if row is not None:
                practice_bank = {
                    "stimulus_set_id": row["stimulus_set_id"],
                    "name": row["name"],
                    "n_items": int(row.get("n_items") or 0),
                    "role": "practice",
                }
        practice_item_count = int(practice_bank.get("n_items") or 0) if practice_bank else 0
        expected_trial_count = compute_expected_trial_count(
            practice_item_count=practice_item_count,
            main_item_count=main_item_count,
        )
        return {
            "aggregation_mode": aggregation_mode,
            "aggregation_enabled": aggregation_mode == AGGREGATION_MODE_MULTI,
            "practice_stimulus_set_id": practice_stimulus_set_id,
            "selected_practice_bank": practice_bank,
            "selected_practice_bank_id": practice_stimulus_set_id,
            "selected_main_stimulus_set_ids": main_stimulus_set_ids,
            "selected_main_bank_ids": main_stimulus_set_ids,
            "banks": banks,
            "practice_bank": practice_bank,
            "practice_item_count": practice_item_count,
            "main_item_count": main_item_count,
            "total_main_items": main_item_count,
            "expected_trial_count": expected_trial_count,
        }
