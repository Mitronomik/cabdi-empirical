"""Session lifecycle service for pilot participant API."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import secrets
from typing import Any
from uuid import uuid4

from app.participant_api.persistence.sqlite_store import dumps, loads
from app.participant_api.persistence.store_protocol import PilotStore
from app.participant_api.services.randomization_service import assign_order_id, build_trial_plan
from app.participant_api.services.run_config_service import resolve_execution_config_from_run
from app.researcher_api.services.run_service import (
    RUN_STATUS_ACTIVE,
    RUN_STATUS_CLOSED,
    RUN_STATUS_DRAFT,
    RUN_STATUS_PAUSED,
)
from packages.shared_types.pilot_types import ParticipantSession, StimulusItem
SESSION_STATUS_CREATED = "created"
SESSION_STATUS_IN_PROGRESS = "in_progress"
SESSION_STATUS_PAUSED = "paused"
SESSION_STATUS_AWAITING_FINAL_SUBMIT = "awaiting_final_submit"
SESSION_STATUS_FINALIZED = "finalized"
SESSION_STATUS_ABANDONED = "abandoned"
TERMINAL_SESSION_STATUSES = {SESSION_STATUS_FINALIZED, "completed"}
RESUMABLE_SESSION_STATUSES = {
    SESSION_STATUS_CREATED,
    SESSION_STATUS_IN_PROGRESS,
    SESSION_STATUS_PAUSED,
    SESSION_STATUS_AWAITING_FINAL_SUBMIT,
}


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

    def create_session(
        self,
        participant_id: str,
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
                }
            if resume_info["resume_status"] == "finalized":
                raise ValueError("resume_not_allowed:session_finalized")

        run_config = loads(run["config_json"])
        experiment = resolve_execution_config_from_run(
            run_config=run_config,
            run_experiment_id=run["experiment_id"],
            run_task_family=run["task_family"],
        )
        stimuli = self._load_run_stimuli(run)
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
            stimulus_set_map={f"set_{idx + 1}": set_id for idx, set_id in enumerate(run["stimulus_set_ids"])},
            current_block_index=-1,
            current_trial_index=0,
            status=SESSION_STATUS_CREATED,
            started_at=_now_iso(),
            completed_at=None,
            device_info={},
            language=normalized_language,
        )

        self.store.execute(
            """
            INSERT INTO participant_sessions(
                session_id, participant_id, experiment_id, run_id, public_session_code, resume_token_hash, assigned_order, stimulus_set_map,
                current_block_index, current_trial_index, status, started_at, completed_at, last_activity_at, device_info, language
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                session.started_at,
                session.completed_at,
                session.started_at,
                dumps(session.device_info),
                session.language,
            ),
        )

        trial_plan = build_trial_plan(participant_id, experiment, assigned_order, [StimulusItem.from_dict(s.to_dict()) for s in stimuli])
        trial_rows = []
        for idx, trial in enumerate(trial_plan):
            trial_id = f"{session_id}_t{idx+1:03d}"
            trial_rows.append(
                (
                    trial_id,
                    session_id,
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
                )
            )
        self.store.executemany(
            """
            INSERT INTO session_trials(
                trial_id, session_id, block_id, block_index, trial_index, condition,
                stimulus_json, pre_render_features_json, risk_bucket, policy_decision_json,
                served_at, completed_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            trial_rows,
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
            SELECT session_id, run_id, status, current_block_index, current_trial_index, public_session_code
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
            }

        return {
            "run_slug": run["public_slug"],
            "resume_status": "not_resumable",
            "session_id": session["session_id"],
            "session_status": session["status"],
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

    def _load_run_stimuli(self, run: dict[str, Any]) -> list[StimulusItem]:
        items: list[StimulusItem] = []
        for stimulus_set_id in run["stimulus_set_ids"]:
            row = self.store.fetchone(
                "SELECT stimulus_set_id, task_family, items_json FROM researcher_stimulus_sets WHERE stimulus_set_id = ?",
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
                items.append(parsed)

        if not items:
            raise ValueError("run has no usable stimuli")
        return items

    def start_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session["status"] in TERMINAL_SESSION_STATUSES | {SESSION_STATUS_AWAITING_FINAL_SUBMIT}:
            return {"session_id": session_id, "status": session["status"]}
        self.store.execute(
            "UPDATE participant_sessions SET status = ?, started_at = ?, last_activity_at = ? WHERE session_id = ?",
            (SESSION_STATUS_IN_PROGRESS, _now_iso(), _now_iso(), session_id),
        )
        return {"session_id": session_id, "status": SESSION_STATUS_IN_PROGRESS}

    def get_session(self, session_id: str) -> dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM participant_sessions WHERE session_id = ?", (session_id,))
        if row is None:
            raise KeyError("session not found")
        row["stimulus_set_map"] = loads(row["stimulus_set_map"])
        row["device_info"] = loads(row["device_info"])
        row["language"] = row.get("language") or "en"
        return row

    def update_progress(self, session_id: str) -> None:
        completed = self.store.fetchall(
            "SELECT block_index, trial_index, block_id FROM session_trials WHERE session_id = ? AND status = 'completed' ORDER BY block_index, trial_index",
            (session_id,),
        )
        if not completed:
            self.store.execute(
                "UPDATE participant_sessions SET current_block_index = ?, current_trial_index = ?, last_activity_at = ? WHERE session_id = ?",
                (-1, 0, _now_iso(), session_id),
            )
            return

        last = completed[-1]
        current_block_index = int(last["block_index"])
        current_trial_index = int(last["trial_index"]) + 1
        self.store.execute(
            "UPDATE participant_sessions SET current_block_index = ?, current_trial_index = ?, last_activity_at = ? WHERE session_id = ?",
            (current_block_index, current_trial_index, _now_iso(), session_id),
        )

    def mark_awaiting_final_submit_if_done(self, session_id: str) -> bool:
        status = self.required_work_status(session_id)
        if not status["eligible"]:
            return False

        self.store.execute(
            "UPDATE participant_sessions SET status = ?, completed_at = NULL, last_activity_at = ? WHERE session_id = ?",
            (SESSION_STATUS_AWAITING_FINAL_SUBMIT, _now_iso(), session_id),
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
        if session["status"] in {SESSION_STATUS_FINALIZED, "completed"}:
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
            "UPDATE participant_sessions SET status = ?, completed_at = ?, last_activity_at = ? WHERE session_id = ?",
            (SESSION_STATUS_FINALIZED, _now_iso(), _now_iso(), session_id),
        )
        return {
            "session_id": session_id,
            "status": SESSION_STATUS_FINALIZED,
            "final_submit": "accepted",
            "already_finalized": False,
        }
