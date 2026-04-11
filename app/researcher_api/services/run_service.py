"""Researcher experiment-run management service."""

from __future__ import annotations

from datetime import datetime, timezone
import os
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
_EMPTY_MAIN_BLOCKS_REASON_TEMPLATE = (
    "run has insufficient main items for configured block design: "
    "main_item_count={main_item_count}, n_blocks={n_blocks}; would produce one or more empty main blocks"
)
_DEFAULT_STALE_SESSION_THRESHOLD_MINUTES = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_stale_session_threshold_minutes(raw: str | None) -> int:
    """Resolve stale-session threshold from env/config with sane bounds."""
    if raw is None or not str(raw).strip():
        return _DEFAULT_STALE_SESSION_THRESHOLD_MINUTES
    try:
        parsed = int(str(raw).strip())
    except ValueError:
        return _DEFAULT_STALE_SESSION_THRESHOLD_MINUTES
    return parsed if parsed > 0 else _DEFAULT_STALE_SESSION_THRESHOLD_MINUTES


def _parse_iso_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_terminal_session_status(status: str) -> bool:
    return status in {"completed", "finalized", "abandoned"}


def build_session_operational_summary(
    sessions: list[dict[str, Any]],
    *,
    stale_session_threshold_minutes: int,
) -> dict[str, Any]:
    """Build canonical session-level operational heuristics for researcher read models."""
    now = datetime.now(timezone.utc)
    stale_session_count = 0
    incomplete_questionnaire_count = 0
    lifecycle_anomaly_count = 0

    for session in sessions:
        raw_status = str(session.get("status") or "")
        status = "finalized" if raw_status == "completed" else raw_status

        if status == "awaiting_final_submit":
            incomplete_questionnaire_count += 1

        started_at = _parse_iso_utc(session.get("started_at"))
        completed_at = _parse_iso_utc(session.get("completed_at"))
        last_activity_at = _parse_iso_utc(session.get("last_activity_at")) or started_at

        if status == "finalized" and completed_at is None:
            lifecycle_anomaly_count += 1
        if completed_at is not None and status != "finalized":
            lifecycle_anomaly_count += 1
        if started_at is not None and completed_at is not None and completed_at < started_at:
            lifecycle_anomaly_count += 1

        if not _is_terminal_session_status(status) and last_activity_at is not None:
            delta_seconds = (now - last_activity_at).total_seconds()
            if delta_seconds > stale_session_threshold_minutes * 60:
                stale_session_count += 1

    return {
        "stale_session_count": stale_session_count,
        "stale_session_threshold_minutes": stale_session_threshold_minutes,
        "incomplete_questionnaire_count": incomplete_questionnaire_count,
        "lifecycle_anomaly_count": lifecycle_anomaly_count,
    }


def compute_expected_trial_count(*, practice_item_count: int, main_item_count: int) -> int:
    return int(practice_item_count) + int(main_item_count)


def validate_non_empty_main_blocks(*, main_item_count: int, n_blocks: int) -> str | None:
    """Return a launchability error message when main-block structure would be empty."""
    normalized_main_item_count = int(main_item_count)
    normalized_n_blocks = int(n_blocks)
    if normalized_n_blocks <= 0:
        return f"run execution config must define n_blocks > 0 (got n_blocks={normalized_n_blocks})"
    if normalized_main_item_count < normalized_n_blocks:
        return _EMPTY_MAIN_BLOCKS_REASON_TEMPLATE.format(
            main_item_count=normalized_main_item_count,
            n_blocks=normalized_n_blocks,
        )
    return None


def compute_run_summary(
    *,
    store: PilotStore,
    main_stimulus_set_ids: list[str],
    practice_stimulus_set_id: str | None,
    aggregation_mode: str,
) -> dict[str, Any]:
    """Compute the canonical run summary contract for researcher and participant services."""
    banks: list[dict[str, Any]] = []
    main_item_count = 0
    for stimulus_set_id in main_stimulus_set_ids:
        row = store.fetchone(
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
        row = store.fetchone(
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
    all_stimulus_set_ids = list(main_stimulus_set_ids)
    if practice_stimulus_set_id:
        all_stimulus_set_ids.append(practice_stimulus_set_id)
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
        "all_stimulus_set_ids": all_stimulus_set_ids,
        "expected_trial_count": expected_trial_count,
    }


class RunService:
    def __init__(
        self,
        store: PilotStore,
        *,
        participant_base_url: str = "http://localhost:5173",
        stale_session_threshold_minutes: int | None = None,
    ) -> None:
        self.store = store
        self.participant_base_url = participant_base_url.rstrip("/")
        self.stale_session_threshold_minutes = (
            stale_session_threshold_minutes
            if stale_session_threshold_minutes is not None
            else _resolve_stale_session_threshold_minutes(os.getenv("PILOT_STALE_SESSION_THRESHOLD_MINUTES"))
        )

    def _invite_url(self, public_slug: str) -> str:
        return f"{self.participant_base_url}/join/{public_slug}"

    @staticmethod
    def _launchability_state(launchable: bool) -> str:
        return "launchable" if launchable else "not_launchable"

    def _compute_activation_readiness_fields(self, run: dict[str, Any]) -> tuple[bool, str]:
        """Return whether a run can be activated now plus canonical reason text."""
        status = str(run.get("status") or RUN_STATUS_DRAFT)
        if status == RUN_STATUS_ACTIVE:
            return False, "run is already active"
        if status == RUN_STATUS_CLOSED:
            return False, "run is closed and cannot be activated"

        validation_errors = self._validate_launchability(run)
        if validation_errors:
            return False, validation_errors[0]
        return True, f"run is {status} and ready to activate"

    def _compute_launchability_fields(self, run: dict[str, Any]) -> tuple[bool, str, str]:
        status = str(run.get("status") or RUN_STATUS_DRAFT)
        if status == RUN_STATUS_ACTIVE:
            launchable = True
            reason = "run is active and accepts participant sessions"
            return launchable, self._launchability_state(launchable), reason
        if status == RUN_STATUS_CLOSED:
            launchable = False
            reason = "run is closed and does not accept new participant sessions"
            return launchable, self._launchability_state(launchable), reason

        validation_errors = self._validate_launchability(run)
        reason = (
            validation_errors[0]
            if validation_errors
            else f"run is {status}; activate to accept new participant sessions"
        )
        launchable = False
        return launchable, self._launchability_state(launchable), reason

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
        task_family: str | None,
        config: dict[str, Any],
        stimulus_set_ids: list[str],
        notes: str | None,
        aggregation_mode: str = AGGREGATION_MODE_SINGLE,
        practice_stimulus_set_id: str | None = None,
        public_slug: str | None = None,
    ) -> dict[str, Any]:
        preview = self.preview_run(
            run_name=run_name,
            public_slug=public_slug,
            experiment_id=experiment_id,
            task_family=task_family,
            stimulus_set_ids=stimulus_set_ids,
            aggregation_mode=aggregation_mode,
            practice_stimulus_set_id=practice_stimulus_set_id,
            config=config,
            notes=notes,
        )
        validation_errors = [str(item) for item in preview.get("validation_errors", [])]
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
        main_stimulus_set_ids = [str(item) for item in preview.get("selected_main_bank_ids", [])]
        resolved_task_family = str(preview.get("resolved_task_family") or "")
        resolved_config = dict(preview.get("resolved_config") or {})
        run_summary = dict(preview.get("run_summary") or {})

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
                resolved_task_family,
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

    def preview_run(
        self,
        *,
        run_name: str,
        public_slug: str | None,
        experiment_id: str,
        task_family: str | None,
        stimulus_set_ids: list[str],
        aggregation_mode: str,
        practice_stimulus_set_id: str | None,
        config: dict[str, Any],
        notes: str | None,
    ) -> dict[str, Any]:
        del public_slug, notes
        validation_errors: list[str] = []
        operator_warnings: list[str] = []
        if not run_name.strip():
            validation_errors.append("run_name must be non-empty")
        if not experiment_id.strip():
            validation_errors.append("experiment_id must be non-empty")
        if aggregation_mode not in _ALLOWED_AGGREGATION_MODES:
            validation_errors.append(f"aggregation_mode must be one of: {sorted(_ALLOWED_AGGREGATION_MODES)}")

        main_stimulus_set_ids = [str(set_id).strip() for set_id in stimulus_set_ids if str(set_id).strip()]
        if not main_stimulus_set_ids:
            validation_errors.append(
                "at least one main stimulus_set_id is required; practice_stimulus_set_id is optional and supplementary only"
            )
        if aggregation_mode == AGGREGATION_MODE_SINGLE and len(main_stimulus_set_ids) != 1:
            validation_errors.append("single aggregation_mode requires exactly one main stimulus_set_id")
        if aggregation_mode == AGGREGATION_MODE_MULTI and len(main_stimulus_set_ids) < 2:
            validation_errors.append("multi aggregation_mode requires at least two main stimulus_set_ids")
        self._collect_no_stimulus_overlap_error(
            validation_errors=validation_errors,
            main_stimulus_set_ids=main_stimulus_set_ids,
            practice_stimulus_set_id=practice_stimulus_set_id,
        )

        selected_banks, resolved_task_family, payload_schema_versions = self._resolve_selected_banks(
            main_stimulus_set_ids=main_stimulus_set_ids,
            practice_stimulus_set_id=practice_stimulus_set_id,
            requested_task_family=task_family,
            validation_errors=validation_errors,
            operator_warnings=operator_warnings,
        )

        default_experiment = load_experiment_config("pilot/configs/default_experiment.yaml")
        resolved_config: dict[str, Any] = {}
        execution_config = None
        if isinstance(config, dict):
            try:
                resolved_config = materialize_run_config_for_storage(
                    run_config=config,
                    default_experiment=default_experiment,
                    experiment_id=experiment_id,
                    task_family=resolved_task_family or str(task_family or ""),
                )
                execution_config = resolve_execution_config_from_run(
                    run_config=resolved_config,
                    run_experiment_id=experiment_id,
                    run_task_family=resolved_task_family or str(task_family or ""),
                )
            except ValueError as exc:
                validation_errors.append(str(exc))
        else:
            validation_errors.append("run.config must be a non-empty object")

        run_summary = self._compute_run_summary(
            main_stimulus_set_ids=main_stimulus_set_ids,
            practice_stimulus_set_id=practice_stimulus_set_id,
            aggregation_mode=aggregation_mode if aggregation_mode in _ALLOWED_AGGREGATION_MODES else AGGREGATION_MODE_SINGLE,
        )
        block_shape_warnings: list[str] = []
        if execution_config is not None:
            non_empty_blocks_error = validate_non_empty_main_blocks(
                main_item_count=int(run_summary.get("main_item_count", 0)),
                n_blocks=int(execution_config.n_blocks),
            )
            if non_empty_blocks_error:
                block_shape_warnings.append(non_empty_blocks_error)
            elif int(run_summary.get("main_item_count", 0)) % int(execution_config.n_blocks) != 0:
                block_shape_warnings.append(
                    "main_item_count does not divide evenly across n_blocks; block sizes will be uneven"
                )

        if payload_schema_versions:
            payload_compatibility = {
                "compatible": len(payload_schema_versions) == 1,
                "selected_versions": sorted(payload_schema_versions),
            }
            if len(payload_schema_versions) > 1:
                validation_errors.append("Selected stimulus sets have incompatible payload_schema_version values")
        else:
            payload_compatibility = {"compatible": True, "selected_versions": []}

        launchability_validation_errors = self._validate_launchability(
            {
                "experiment_id": experiment_id,
                "task_family": resolved_task_family,
                "config": resolved_config,
                "stimulus_set_ids": main_stimulus_set_ids,
                "aggregation_mode": aggregation_mode,
                "practice_stimulus_set_id": practice_stimulus_set_id,
                "run_summary": run_summary,
            }
        )
        launchability_preview = {
            "launchable": len(launchability_validation_errors) == 0 and len(validation_errors) == 0,
            "launchability_state": self._launchability_state(
                len(launchability_validation_errors) == 0 and len(validation_errors) == 0
            ),
            "launchability_reason": (
                "run can be activated once created"
                if len(launchability_validation_errors) == 0 and len(validation_errors) == 0
                else (launchability_validation_errors[0] if launchability_validation_errors else validation_errors[0])
            ),
            "validation_errors": launchability_validation_errors,
        }
        selection_summary = self._build_preview_selection_summary(
            selected_banks=selected_banks,
            resolved_task_family=resolved_task_family,
            validation_errors=validation_errors,
        )

        return {
            "resolved_task_family": resolved_task_family,
            "validation_errors": validation_errors,
            "operator_warnings": operator_warnings,
            "selected_banks": selected_banks,
            "selected_main_bank_ids": main_stimulus_set_ids,
            "selected_practice_bank_id": practice_stimulus_set_id,
            "practice_item_count": int(run_summary.get("practice_item_count", 0)),
            "main_item_count": int(run_summary.get("main_item_count", 0)),
            "expected_trial_count": int(run_summary.get("expected_trial_count", 0)),
            "launchability_preview": launchability_preview,
            "payload_schema_compatibility": payload_compatibility,
            "block_shape_warnings": block_shape_warnings,
            "run_summary": run_summary,
            "resolved_config": resolved_config,
            "selection_summary": selection_summary,
        }

    def _build_preview_selection_summary(
        self,
        *,
        selected_banks: list[dict[str, Any]],
        resolved_task_family: str,
        validation_errors: list[str],
    ) -> dict[str, Any]:
        main_banks = [bank for bank in selected_banks if str(bank.get("role") or "") == "main"]
        practice_bank = next((bank for bank in selected_banks if str(bank.get("role") or "") == "practice"), None)
        has_mixed_family_error = any("mixed task families" in str(message).lower() for message in validation_errors)
        return {
            "main_banks": main_banks,
            "practice_bank": practice_bank,
            "main_bank_summary_label": ", ".join(
                f"{str(bank.get('name') or '')} ({int(bank.get('n_items') or 0)})" for bank in main_banks
            ),
            "task_family_field_state": (
                "mixed_invalid" if has_mixed_family_error else ("resolved" if resolved_task_family else "unresolved")
            ),
            "task_family_field_value": resolved_task_family,
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
        row["accepting_sessions_now"] = str(row.get("status") or RUN_STATUS_DRAFT) == RUN_STATUS_ACTIVE
        row["ready_to_activate"], row["activation_readiness_reason"] = self._compute_activation_readiness_fields(row)
        row["launchable"], row["launchability_state"], row["launchability_reason"] = self._compute_launchability_fields(
            row
        )
        row["run_status"] = row["status"]
        row["invite_url"] = self._invite_url(str(row["public_slug"]))
        return row

    def list_runs(self) -> list[dict[str, Any]]:
        rows = self.store.fetchall(
            """
            SELECT run_id, run_name, public_slug, status, experiment_id, task_family, notes, created_at, stimulus_set_ids_json
                   , config_json
                   , aggregation_mode, practice_stimulus_set_id
            FROM researcher_runs
            ORDER BY created_at DESC
            """,
            (),
        )
        for row in rows:
            row["linked_stimulus_set_ids"] = loads(row.pop("stimulus_set_ids_json"))
            row["config"] = loads(row.pop("config_json"))
            aggregation_mode = AGGREGATION_MODE_MULTI if int(row.get("aggregation_mode") or 0) == 1 else AGGREGATION_MODE_SINGLE
            row["aggregation_mode"] = aggregation_mode
            row["practice_stimulus_set_id"] = row.get("practice_stimulus_set_id")
            row["run_summary"] = self._compute_run_summary(
                main_stimulus_set_ids=row["linked_stimulus_set_ids"],
                practice_stimulus_set_id=row["practice_stimulus_set_id"],
                aggregation_mode=aggregation_mode,
            )
            row["stimulus_set_ids"] = row["linked_stimulus_set_ids"]
            row["accepting_sessions_now"] = str(row.get("status") or RUN_STATUS_DRAFT) == RUN_STATUS_ACTIVE
            row["ready_to_activate"], row["activation_readiness_reason"] = self._compute_activation_readiness_fields(row)
            row["launchable"], row["launchability_state"], row["launchability_reason"] = self._compute_launchability_fields(
                row
            )
            row.pop("stimulus_set_ids", None)
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
            "accepting_sessions_now": run["accepting_sessions_now"],
            "ready_to_activate": run["ready_to_activate"],
            "activation_readiness_reason": run["activation_readiness_reason"],
            "launchable": run["launchable"],
            "launchability_state": run["launchability_state"],
            "launchability_reason": run["launchability_reason"],
            "task_family": run["task_family"],
            "linked_stimulus_set_ids": run["stimulus_set_ids"],
            "validation_errors": validation_errors,
        }

    def _validate_launchability(self, run: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        execution_config = None
        if not str(run.get("experiment_id", "")).strip():
            errors.append("run.experiment_id must be non-empty")
        if not str(run.get("task_family", "")).strip():
            errors.append("run.task_family must be non-empty")

        config = run.get("config")
        if not isinstance(config, dict) or not config:
            errors.append("run.config must be a non-empty object")
        else:
            try:
                execution_config = resolve_execution_config_from_run(
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
        practice_stimulus_set_id = run.get("practice_stimulus_set_id")
        if practice_stimulus_set_id and practice_stimulus_set_id in stimulus_set_ids:
            errors.append("practice_stimulus_set_id must not overlap with main stimulus_set_ids")

        run_summary = run.get("run_summary")
        if not isinstance(run_summary, dict):
            errors.append("run summary missing")
        else:
            expected_total = int(run_summary.get("expected_trial_count", 0))
            if expected_total <= 0:
                errors.append("run summary expected_trial_count must be positive")
            if execution_config is not None:
                non_empty_blocks_error = validate_non_empty_main_blocks(
                    main_item_count=int(run_summary.get("main_item_count", 0)),
                    n_blocks=int(execution_config.n_blocks),
                )
                if non_empty_blocks_error:
                    errors.append(non_empty_blocks_error)

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
        operational_summary = build_session_operational_summary(
            rows,
            stale_session_threshold_minutes=self.stale_session_threshold_minutes,
        )
        return {
            "run_id": run_id,
            "public_slug": run["public_slug"],
            "run_status": run["status"],
            "counts": counts,
            "mean_completion_seconds": mean_completion_seconds,
            "stale_session_count": int(operational_summary["stale_session_count"]),
            "operational_summary": operational_summary,
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
        self._validate_no_stimulus_overlap(
            main_stimulus_set_ids=main_stimulus_set_ids,
            practice_stimulus_set_id=practice_stimulus_set_id,
        )
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

    @staticmethod
    def _validate_no_stimulus_overlap(*, main_stimulus_set_ids: list[str], practice_stimulus_set_id: str | None) -> None:
        if practice_stimulus_set_id and practice_stimulus_set_id in main_stimulus_set_ids:
            raise ValueError("practice_stimulus_set_id must not overlap with main stimulus_set_ids")

    @staticmethod
    def _collect_no_stimulus_overlap_error(
        *,
        validation_errors: list[str],
        main_stimulus_set_ids: list[str],
        practice_stimulus_set_id: str | None,
    ) -> None:
        try:
            RunService._validate_no_stimulus_overlap(
                main_stimulus_set_ids=main_stimulus_set_ids,
                practice_stimulus_set_id=practice_stimulus_set_id,
            )
        except ValueError as exc:
            validation_errors.append(str(exc))

    def _resolve_selected_banks(
        self,
        *,
        main_stimulus_set_ids: list[str],
        practice_stimulus_set_id: str | None,
        requested_task_family: str | None,
        validation_errors: list[str],
        operator_warnings: list[str],
    ) -> tuple[list[dict[str, Any]], str, set[str]]:
        selected_banks: list[dict[str, Any]] = []
        payload_versions: set[str] = set()
        task_families: set[str] = set()
        all_set_ids = list(main_stimulus_set_ids)
        if practice_stimulus_set_id:
            all_set_ids.append(practice_stimulus_set_id)
        for stimulus_set_id in all_set_ids:
            row = self.store.fetchone(
                """
                SELECT stimulus_set_id, name, task_family, validation_status, n_items, payload_schema_version
                FROM researcher_stimulus_sets
                WHERE stimulus_set_id = ?
                """,
                (stimulus_set_id,),
            )
            role = "practice" if practice_stimulus_set_id and stimulus_set_id == practice_stimulus_set_id else "main"
            if row is None:
                validation_errors.append(f"Unknown stimulus_set_id: {stimulus_set_id}")
                continue
            resolved_task_family = str(row.get("task_family") or "")
            if resolved_task_family:
                task_families.add(resolved_task_family)
            payload_versions.add(str(row.get("payload_schema_version") or "stimulus_payload.v1"))
            if row.get("validation_status") not in {"valid", "warning_only"}:
                validation_errors.append(f"Stimulus set is not run-compatible: {stimulus_set_id}")
            if row.get("validation_status") == "warning_only":
                operator_warnings.append(
                    f"Stimulus set has warning_only validation status: {stimulus_set_id}"
                )
            selected_banks.append(
                {
                    "stimulus_set_id": row["stimulus_set_id"],
                    "name": row["name"],
                    "n_items": int(row.get("n_items") or 0),
                    "task_family": resolved_task_family,
                    "validation_status": row.get("validation_status"),
                    "payload_schema_version": str(row.get("payload_schema_version") or "stimulus_payload.v1"),
                    "role": role,
                }
            )

        requested_family = str(requested_task_family or "").strip()
        if requested_family:
            if any(family != requested_family for family in task_families):
                validation_errors.append("All selected stimulus sets must match run task_family")
            resolved_family = requested_family
        else:
            if len(task_families) > 1:
                validation_errors.append(
                    "Selected main banks have mixed task families. Choose banks with one shared task family."
                )
                resolved_family = ""
            elif len(task_families) == 1:
                resolved_family = next(iter(task_families))
            else:
                resolved_family = ""
        if not resolved_family:
            validation_errors.append("task_family must be non-empty")
        return selected_banks, resolved_family, payload_versions

    def _compute_run_summary(
        self,
        *,
        main_stimulus_set_ids: list[str],
        practice_stimulus_set_id: str | None,
        aggregation_mode: str,
    ) -> dict[str, Any]:
        return compute_run_summary(
            store=self.store,
            main_stimulus_set_ids=main_stimulus_set_ids,
            practice_stimulus_set_id=practice_stimulus_set_id,
            aggregation_mode=aggregation_mode,
        )
