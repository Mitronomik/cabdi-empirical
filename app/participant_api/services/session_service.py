"""Session lifecycle service for pilot participant API."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import secrets
from typing import Any
from uuid import uuid4

from app.participant_api.persistence.json_codec import dumps, loads
from app.participant_api.persistence.store_protocol import PilotStore
from app.participant_api.services.randomization_service import assign_order_id, build_trial_plan
from app.participant_api.services.run_config_service import resolve_execution_config_from_run
from app.researcher_api.services.run_service import (
    RUN_STATUS_ACTIVE,
    RUN_STATUS_CLOSED,
    RUN_STATUS_DRAFT,
    RUN_STATUS_PAUSED,
    compute_run_summary,
)
from packages.shared_types.pilot_types import (
    RESUMABLE_SESSION_STATUSES,
    ExperimentConfig,
    SESSION_STATUS_AWAITING_FINAL_SUBMIT,
    SESSION_STATUS_COMPLETED_LEGACY,
    SESSION_STATUS_CREATED,
    SESSION_STATUS_FINALIZED,
    SESSION_STATUS_IN_PROGRESS,
    SESSION_STATUS_PAUSED,
    TERMINAL_SESSION_STATUSES,
    ParticipantSession,
    StimulusItem,
)

SESSION_STAGE_CONSENT = "consent"
SESSION_STAGE_INSTRUCTIONS = "instructions"
SESSION_STAGE_PRACTICE = "practice"
SESSION_STAGE_TRIAL = "trial"
SESSION_STAGE_QUESTIONNAIRE = "questionnaire"
SESSION_STAGE_AWAITING_FINAL_SUBMIT = "awaiting_final_submit"
SESSION_STAGE_COMPLETION = "completion"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionService:
    def __init__(self, store: PilotStore) -> None:
        self.store = store

    @staticmethod
    def _normalize_language(language: str | None) -> str:
        if language in {"en", "ru"}:
            return language
        return "en"

    @staticmethod
    def _normalize_runtime_status(status: str) -> str:
        # Legacy compatibility: historical rows may still use "completed".
        if status == SESSION_STATUS_COMPLETED_LEGACY:
            return SESSION_STATUS_FINALIZED
        return status

    def create_session(
        self,
        run_slug: str,
        language: str | None = None,
        resume_token: str | None = None,
    ) -> dict[str, Any]:
        run = self._resolve_public_run(run_slug=run_slug)
        if resume_token:
            resume_info = self.get_resume_info(run_slug=run_slug, resume_token=resume_token)
            if resume_info["resume_status"] == "resumable":
                session = self.get_session(str(resume_info["session_id"]))
                return {
                    "session_id": session["session_id"],
                    "status": session["status"],
                    "assigned_order": session["assigned_order"],
                    "run_slug": run["public_slug"],
                    "language": session.get("language") or "en",
                    "entry_mode": "resumed",
                    "public_session_code": session.get("public_session_code"),
                    "resume_token": resume_token,
                    "current_stage": session.get("current_stage") or SESSION_STAGE_CONSENT,
                }
            if resume_info["resume_status"] == "finalized":
                raise ValueError("resume_not_allowed:session_finalized")

        run_config = loads(run["config_json"])
        experiment = resolve_execution_config_from_run(
            run_config=run_config,
            run_experiment_id=run["experiment_id"],
            run_task_family=run["task_family"],
        )
        run_summary = self._compute_run_summary(run)
        participant_id = self._generate_participant_id()
        order_id, assigned_order = assign_order_id(participant_id, experiment.experiment_id)
        session_id = f"sess_{uuid4().hex[:12]}"
        public_session_code = self._generate_public_session_code()
        resolved_resume_token = self._generate_resume_token()
        normalized_language = self._normalize_language(language)

        session = ParticipantSession(
            session_id=session_id,
            participant_id=participant_id,
            experiment_id=run["experiment_id"],
            run_id=run["run_id"],
            assigned_order=order_id,
            stimulus_set_map={f"set_{idx + 1}": set_id for idx, set_id in enumerate(run_summary["selected_main_stimulus_set_ids"])},
            current_block_index=-1,
            current_trial_index=0,
            status=SESSION_STATUS_CREATED,
            created_at=_now_iso(),
            started_at=None,
            completed_at=None,
            device_info={},
            language=normalized_language,
        )

        self.store.execute(
            """
            INSERT INTO participant_sessions(
                session_id, participant_id, experiment_id, run_id, public_session_code, resume_token_hash, assigned_order, stimulus_set_map,
                current_block_index, current_trial_index, status, current_stage, created_at, started_at, completed_at, consent_at, finalized_at,
                last_activity_at, device_info, language,
                expected_trial_count, source_stimulus_set_ids_json, snapshot_frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.session_id,
                session.participant_id,
                session.experiment_id,
                session.run_id,
                public_session_code,
                self._hash_resume_token(resolved_resume_token),
                session.assigned_order,
                dumps(session.stimulus_set_map),
                session.current_block_index,
                session.current_trial_index,
                session.status,
                SESSION_STAGE_CONSENT,
                session.created_at,
                session.started_at,
                session.completed_at,
                None,
                None,
                session.created_at,
                dumps(session.device_info),
                session.language,
                int(run_summary["expected_trial_count"]),
                dumps(run_summary["all_stimulus_set_ids"]),
                None,
            ),
        )

        return {
            "session_id": session_id,
            "status": SESSION_STATUS_CREATED,
            "assigned_order": order_id,
            "run_slug": run["public_slug"],
            "language": session.language,
            "entry_mode": "created",
            "public_session_code": public_session_code,
            "resume_token": resolved_resume_token,
            "current_stage": SESSION_STAGE_CONSENT,
        }

    @staticmethod
    def _hash_resume_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _generate_resume_token() -> str:
        return secrets.token_urlsafe(24)

    def _generate_public_session_code(self) -> str:
        while True:
            candidate = secrets.token_hex(4).upper()
            existing = self.store.fetchone(
                "SELECT session_id FROM participant_sessions WHERE public_session_code = ?",
                (candidate,),
            )
            if existing is None:
                return candidate

    def _generate_participant_id(self) -> str:
        while True:
            candidate = f"anon_{secrets.token_hex(8)}"
            existing = self.store.fetchone(
                "SELECT session_id FROM participant_sessions WHERE participant_id = ? LIMIT 1",
                (candidate,),
            )
            if existing is None:
                return candidate

    def get_resume_info(self, run_slug: str, resume_token: str) -> dict[str, Any]:
        normalized_run_slug = (run_slug or "").strip()
        if not normalized_run_slug:
            raise ValueError("run_slug is required")
        normalized_resume_token = (resume_token or "").strip()
        if not normalized_resume_token:
            raise ValueError("resume_token is required")
        run = self.store.fetchone(
            "SELECT run_id, public_slug FROM researcher_runs WHERE public_slug = ?",
            (normalized_run_slug,),
        )
        if run is None:
            raise KeyError("run not found")

        session = self.store.fetchone(
            """
            SELECT session_id, run_id, status, current_stage, current_block_index, current_trial_index, public_session_code
            FROM participant_sessions
            WHERE run_id = ? AND resume_token_hash = ?
            """,
            (run["run_id"], self._hash_resume_token(normalized_resume_token)),
        )
        if session is None:
            return {"run_slug": run["public_slug"], "resume_status": "invalid"}

        if session["status"] in RESUMABLE_SESSION_STATUSES:
            return {
                "run_slug": run["public_slug"],
                "resume_status": "resumable",
                "session_id": session["session_id"],
                "session_status": session["status"],
                "public_session_code": session.get("public_session_code"),
                "current_stage": session.get("current_stage") or SESSION_STAGE_CONSENT,
                "current_block_index": session["current_block_index"],
                "current_trial_index": session["current_trial_index"],
            }

        if session["status"] in TERMINAL_SESSION_STATUSES:
            return {
                "run_slug": run["public_slug"],
                "resume_status": "finalized",
                "session_id": session["session_id"],
                "session_status": SESSION_STATUS_FINALIZED,
                "public_session_code": session.get("public_session_code"),
                "current_stage": SESSION_STAGE_COMPLETION,
            }

        return {
            "run_slug": run["public_slug"],
            "resume_status": "not_resumable",
            "session_id": session["session_id"],
            "session_status": session["status"],
            "public_session_code": session.get("public_session_code"),
            "current_stage": session.get("current_stage") or SESSION_STAGE_CONSENT,
        }

    def resume_session(self, run_slug: str, resume_token: str) -> dict[str, Any]:
        resume_info = self.get_resume_info(run_slug=run_slug, resume_token=resume_token)
        if resume_info["resume_status"] != "resumable":
            return resume_info
        session = self.get_session(str(resume_info["session_id"]))
        return {
            "resume_status": "resumable",
            "session_id": session["session_id"],
            "session_status": session["status"],
            "current_stage": session.get("current_stage") or SESSION_STAGE_CONSENT,
            "current_block_index": int(session.get("current_block_index", -1)),
            "current_trial_index": int(session.get("current_trial_index", 0)),
            "public_session_code": session.get("public_session_code"),
        }

    def _resolve_public_run(self, *, run_slug: str) -> dict[str, Any]:
        normalized_run_slug = (run_slug or "").strip()
        if not normalized_run_slug:
            raise ValueError("run_slug is required")
        run = self.store.fetchone("SELECT * FROM researcher_runs WHERE public_slug = ?", (normalized_run_slug,))
        if run is None:
            raise ValueError(f"Unknown run_slug: {normalized_run_slug}")

        status = run.get("status")
        if status == RUN_STATUS_DRAFT:
            raise ValueError(f"run_slug '{normalized_run_slug}' is not launchable: status is draft")
        if status == RUN_STATUS_PAUSED:
            raise ValueError(f"run_slug '{normalized_run_slug}' is not launchable: status is paused")
        if status == RUN_STATUS_CLOSED:
            raise ValueError(f"run_slug '{normalized_run_slug}' is not launchable: status is closed")
        if status != RUN_STATUS_ACTIVE:
            raise ValueError(f"run_slug '{normalized_run_slug}' is not launchable: status is {status}")

        config = loads(run["config_json"])
        if not isinstance(config, dict) or not config:
            raise ValueError("run is missing required config for participant execution")

        run["stimulus_set_ids"] = loads(run["stimulus_set_ids_json"])
        if not isinstance(run["stimulus_set_ids"], list) or not run["stimulus_set_ids"]:
            raise ValueError("run does not reference any stimulus sets")
        run["aggregation_mode"] = "multi" if int(run.get("aggregation_mode") or 0) == 1 else "single"
        run["practice_stimulus_set_id"] = run.get("practice_stimulus_set_id")
        return run

    def get_public_run_info(self, run_slug: str) -> dict[str, Any]:
        run = self.store.fetchone(
            "SELECT run_name, public_slug, status, config_json FROM researcher_runs WHERE public_slug = ?",
            (run_slug.strip(),),
        )
        if run is None:
            raise KeyError("run not found")

        config = loads(run["config_json"])
        if not isinstance(config, dict):
            config = {}
        return {
            "run_slug": run["public_slug"],
            "public_title": run["run_name"],
            "public_description": config.get("public_description") or config.get("instructions_summary"),
            "launchable": run["status"] == RUN_STATUS_ACTIVE,
            "run_status": run["status"],
        }

    def _load_stimuli_for_set_ids(self, *, run: dict[str, Any], stimulus_set_ids: list[str]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for stimulus_set_id in stimulus_set_ids:
            row = self.store.fetchone(
                "SELECT stimulus_set_id, task_family, items_json, payload_schema_version FROM researcher_stimulus_sets WHERE stimulus_set_id = ?",
                (stimulus_set_id,),
            )
            if row is None:
                raise ValueError(f"run references missing stimulus_set_id: {stimulus_set_id}")
            if row["task_family"] != run["task_family"]:
                raise ValueError("run stimulus set task_family mismatch")
            for raw_item in loads(row["items_json"]):
                parsed = StimulusItem.from_dict(raw_item)
                if parsed.task_family != run["task_family"]:
                    raise ValueError(f"stimulus {parsed.stimulus_id} task_family mismatches run task_family")
                items.append(
                    {
                        "stimulus": parsed,
                        "source_stimulus_set_ids": [stimulus_set_id],
                        "payload_schema_version": row.get("payload_schema_version") or "stimulus_payload.v1",
                    }
                )

        if not items:
            raise ValueError("run has no usable stimuli")
        return items

    def _compute_run_summary(self, run: dict[str, Any]) -> dict[str, Any]:
        return compute_run_summary(
            store=self.store,
            main_stimulus_set_ids=list(run["stimulus_set_ids"]),
            practice_stimulus_set_id=run.get("practice_stimulus_set_id"),
            aggregation_mode=str(run.get("aggregation_mode") or "single"),
        )

    def _build_session_trial_snapshot(self, *, session: dict[str, Any], run: dict[str, Any]) -> None:
        run_config = loads(run["config_json"])
        base_experiment = resolve_execution_config_from_run(
            run_config=run_config,
            run_experiment_id=run["experiment_id"],
            run_task_family=run["task_family"],
        )
        run_summary = self._compute_run_summary(run)
        main_item_count = int(run_summary["main_item_count"])
        practice_item_count = int(run_summary["practice_item_count"])
        if main_item_count <= 0:
            raise ValueError("run has no main items available for snapshot generation")
        main_trials_per_block = self._distribute_main_trials_per_block(
            total_main_trials=main_item_count,
            n_blocks=base_experiment.n_blocks,
        )
        main_stimuli = self._load_stimuli_for_set_ids(run=run, stimulus_set_ids=list(run["stimulus_set_ids"]))
        practice_stimulus_set_id = run.get("practice_stimulus_set_id")
        practice_stimuli = (
            self._load_stimuli_for_set_ids(run=run, stimulus_set_ids=[str(practice_stimulus_set_id)])
            if practice_stimulus_set_id
            else []
        )
        source_map: dict[str, list[str]] = {}
        for row in [*main_stimuli, *practice_stimuli]:
            stimulus = row["stimulus"]
            source_map[stimulus.stimulus_id] = list(row["source_stimulus_set_ids"])
        trial_plan = build_trial_plan(
            session["participant_id"],
            base_experiment,
            assign_order_id(session["participant_id"], base_experiment.experiment_id)[1],
            [StimulusItem.from_dict(item["stimulus"].to_dict()) for item in main_stimuli],
            practice_stimuli=[StimulusItem.from_dict(item["stimulus"].to_dict()) for item in practice_stimuli],
            stimulus_source_map=source_map,
            practice_trials_override=practice_item_count,
            main_trials_per_block_override=main_trials_per_block,
        )
        expected_trial_count = int(run_summary["expected_trial_count"])
        if len(trial_plan) != expected_trial_count:
            raise ValueError("session trial snapshot mismatch: trial plan length does not match run summary")
        if self.store.fetchone("SELECT trial_id FROM session_trials WHERE session_id = ? LIMIT 1", (session["session_id"],)) is not None:
            return

        all_source_ids = list(run_summary["all_stimulus_set_ids"])
        payload_versions = {
            str(item.get("payload_schema_version") or "stimulus_payload.v1")
            for item in [*main_stimuli, *practice_stimuli]
        }
        payload_schema_version = sorted(payload_versions)[0] if payload_versions else "stimulus_payload.v1"

        trial_rows = []
        for idx, trial in enumerate(trial_plan):
            trial_id = f"{session['session_id']}_t{idx+1:03d}"
            trial_rows.append(
                (
                    trial_id,
                    session["session_id"],
                    trial["block_id"],
                    int(trial["block_index"]),
                    int(trial["trial_index"]),
                    trial["condition"],
                    dumps(trial["stimulus"]),
                    dumps(trial["pre_render_features"]),
                    None,
                    None,
                    None,
                    None,
                    "pending",
                    expected_trial_count,
                    dumps(trial.get("source_stimulus_set_ids") or []),
                    1 if str(trial["block_id"]) == "practice" else 0,
                    payload_schema_version,
                )
            )
        self.store.executemany(
            """
            INSERT INTO session_trials(
                trial_id, session_id, block_id, block_index, trial_index, condition,
                stimulus_json, pre_render_features_json, risk_bucket, policy_decision_json,
                served_at, completed_at, status, expected_trial_count, source_stimulus_set_ids_json,
                is_practice, payload_schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            trial_rows,
        )
        self.store.execute(
            "UPDATE participant_sessions SET expected_trial_count = ?, source_stimulus_set_ids_json = ?, snapshot_frozen_at = ? WHERE session_id = ?",
            (expected_trial_count, dumps(all_source_ids), _now_iso(), session["session_id"]),
        )

    @staticmethod
    def _distribute_main_trials_per_block(*, total_main_trials: int, n_blocks: int) -> list[int]:
        if n_blocks <= 0:
            raise ValueError("n_blocks must be > 0")
        if total_main_trials < 0:
            raise ValueError("total_main_trials must be >= 0")
        base = total_main_trials // n_blocks
        remainder = total_main_trials % n_blocks
        out = [base] * n_blocks
        for idx in range(remainder):
            out[idx] += 1
        return out

    def start_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if not str(session.get("run_id") or "").strip():
            raise ValueError("session cannot start without run_id")
        run = self.store.fetchone("SELECT * FROM researcher_runs WHERE run_id = ?", (session["run_id"],))
        if run is None:
            raise ValueError("session run reference is invalid")
        run["stimulus_set_ids"] = loads(run["stimulus_set_ids_json"])
        run["aggregation_mode"] = "multi" if int(run.get("aggregation_mode") or 0) == 1 else "single"
        if run["aggregation_mode"] == "single" and len(run["stimulus_set_ids"]) != 1:
            raise ValueError("single-set run cannot include more than one main stimulus set")
        if run["aggregation_mode"] == "multi" and len(run["stimulus_set_ids"]) < 2:
            raise ValueError("multi-set run requires at least two main stimulus sets")

        self._build_session_trial_snapshot(session=session, run=run)
        actual_trial_count = self.store.fetchone(
            "SELECT COUNT(*) AS n FROM session_trials WHERE session_id = ?",
            (session_id,),
        )
        if int(actual_trial_count["n"]) != int(session["expected_trial_count"]):
            raise ValueError("session trial snapshot count does not match expected trial count")
        runtime_status = self._normalize_runtime_status(session["status"])
        if runtime_status in TERMINAL_SESSION_STATUSES | {SESSION_STATUS_AWAITING_FINAL_SUBMIT}:
            return {"session_id": session_id, "status": runtime_status}
        if runtime_status not in {SESSION_STATUS_CREATED, SESSION_STATUS_IN_PROGRESS, SESSION_STATUS_PAUSED}:
            return {"session_id": session_id, "status": session["status"]}
        now_iso = _now_iso()
        if runtime_status == SESSION_STATUS_CREATED:
            practice_trial_count = self.store.fetchone(
                "SELECT COUNT(*) AS n FROM session_trials WHERE session_id = ? AND is_practice = 1",
                (session_id,),
            )
            initial_stage = SESSION_STAGE_PRACTICE if int(practice_trial_count["n"]) > 0 else SESSION_STAGE_TRIAL
            self.store.execute(
                """
                UPDATE participant_sessions
                SET status = ?, started_at = COALESCE(started_at, ?), consent_at = COALESCE(consent_at, ?), current_stage = ?, last_activity_at = ?
                WHERE session_id = ?
                """,
                (SESSION_STATUS_IN_PROGRESS, now_iso, now_iso, initial_stage, now_iso, session_id),
            )
        else:
            self.store.execute(
                """
                UPDATE participant_sessions
                SET status = ?, started_at = COALESCE(started_at, ?), consent_at = COALESCE(consent_at, ?), last_activity_at = ?
                WHERE session_id = ?
                """,
                (SESSION_STATUS_IN_PROGRESS, now_iso, now_iso, now_iso, session_id),
            )
        return {"session_id": session_id, "status": SESSION_STATUS_IN_PROGRESS}

    def get_session(self, session_id: str) -> dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM participant_sessions WHERE session_id = ?", (session_id,))
        if row is None:
            raise KeyError("session not found")
        row["stimulus_set_map"] = loads(row["stimulus_set_map"])
        row["device_info"] = loads(row["device_info"])
        row["source_stimulus_set_ids"] = loads(row.get("source_stimulus_set_ids_json") or "[]")
        row["language"] = row.get("language") or "en"
        row["status"] = self._normalize_runtime_status(str(row["status"]))
        row["current_stage"] = row.get("current_stage") or SESSION_STAGE_CONSENT
        return row

    def update_progress(self, session_id: str) -> None:
        completed = self.store.fetchall(
            "SELECT block_index, trial_index, block_id FROM session_trials WHERE session_id = ? AND status = 'completed' ORDER BY block_index, trial_index",
            (session_id,),
        )
        if not completed:
            self.store.execute(
                """
                UPDATE participant_sessions
                SET current_block_index = ?, current_trial_index = ?, current_stage = ?, last_activity_at = ?
                WHERE session_id = ?
                """,
                (-1, 0, SESSION_STAGE_PRACTICE, _now_iso(), session_id),
            )
            return

        last = completed[-1]
        current_block_index = int(last["block_index"])
        current_trial_index = int(last["trial_index"]) + 1
        current_stage = SESSION_STAGE_PRACTICE if current_block_index < 0 else SESSION_STAGE_TRIAL
        self.store.execute(
            """
            UPDATE participant_sessions
            SET current_block_index = ?, current_trial_index = ?, current_stage = ?, last_activity_at = ?
            WHERE session_id = ?
            """,
            (current_block_index, current_trial_index, current_stage, _now_iso(), session_id),
        )

    def mark_awaiting_final_submit_if_done(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        runtime_status = self._normalize_runtime_status(session["status"])
        if runtime_status in TERMINAL_SESSION_STATUSES:
            return False
        if runtime_status == SESSION_STATUS_AWAITING_FINAL_SUBMIT:
            return True

        status = self.required_work_status(session_id)
        if not status["eligible"]:
            return False

        self.store.execute(
            """
            UPDATE participant_sessions
            SET status = ?, current_stage = ?, completed_at = NULL, last_activity_at = ?
            WHERE session_id = ?
            """,
            (SESSION_STATUS_AWAITING_FINAL_SUBMIT, SESSION_STAGE_AWAITING_FINAL_SUBMIT, _now_iso(), session_id),
        )
        return True

    def required_work_status(self, session_id: str) -> dict[str, Any]:
        pending = self.store.fetchone(
            "SELECT trial_id FROM session_trials WHERE session_id = ? AND status != 'completed' LIMIT 1",
            (session_id,),
        )
        has_incomplete_trials = pending is not None

        main_blocks = self.store.fetchall(
            "SELECT DISTINCT block_id FROM session_trials WHERE session_id = ? AND block_id != 'practice'",
            (session_id,),
        )
        missing_questionnaire_blocks: list[str] = []
        for block in main_blocks:
            q = self.store.fetchone(
                "SELECT questionnaire_id FROM block_questionnaires WHERE session_id = ? AND block_id = ?",
                (session_id, block["block_id"]),
            )
            if q is None:
                missing_questionnaire_blocks.append(str(block["block_id"]))

        return {
            "eligible": not has_incomplete_trials and not missing_questionnaire_blocks,
            "has_incomplete_trials": has_incomplete_trials,
            "missing_questionnaire_blocks": sorted(missing_questionnaire_blocks),
        }

    def final_submit(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if self._normalize_runtime_status(session["status"]) == SESSION_STATUS_FINALIZED:
            return {
                "session_id": session_id,
                "status": SESSION_STATUS_FINALIZED,
                "final_submit": "already_finalized",
                "already_finalized": True,
            }

        work_status = self.required_work_status(session_id)
        if work_status["has_incomplete_trials"]:
            raise ValueError("final_submit_ineligible:incomplete_trials")
        if work_status["missing_questionnaire_blocks"]:
            missing_blocks = ",".join(work_status["missing_questionnaire_blocks"])
            raise ValueError(f"final_submit_ineligible:missing_block_questionnaires:{missing_blocks}")

        self.store.execute(
            """
            UPDATE participant_sessions
            SET status = ?, current_stage = ?, completed_at = ?, finalized_at = ?, last_activity_at = ?
            WHERE session_id = ?
            """,
            (SESSION_STATUS_FINALIZED, SESSION_STAGE_COMPLETION, _now_iso(), _now_iso(), _now_iso(), session_id),
        )
        return {
            "session_id": session_id,
            "status": SESSION_STATUS_FINALIZED,
            "final_submit": "accepted",
            "already_finalized": False,
        }

    def mark_questionnaire_stage(self, session_id: str, block_id: str) -> None:
        self.store.execute(
            """
            UPDATE participant_sessions
            SET current_stage = ?, current_block_index = CAST(SUBSTR(?, 7) AS INTEGER) - 1, current_trial_index = 0, last_activity_at = ?
            WHERE session_id = ?
            """,
            (SESSION_STAGE_QUESTIONNAIRE, block_id, _now_iso(), session_id),
        )

    def get_progress_info(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        return {
            "session_id": session_id,
            "status": session["status"],
            "current_stage": session.get("current_stage") or SESSION_STAGE_CONSENT,
            "current_block_index": int(session.get("current_block_index", -1)),
            "current_trial_index": int(session.get("current_trial_index", 0)),
            "consent_at": session.get("consent_at"),
            "last_activity_at": session.get("last_activity_at"),
            "finalized_at": session.get("finalized_at"),
            "public_session_code": session.get("public_session_code"),
        }
