"""Run-level researcher exports built from existing session artifacts."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from analysis.pilot.derive_metrics import derive_trial_level_rows
from analysis.pilot.exclusions import compute_exclusion_flags
from analysis.pilot.mixed_effects_ready import build_mixed_effects_ready
from analysis.pilot.report_builder import build_report
from analysis.pilot.summaries import build_participant_summary
from app.participant_api.persistence.sqlite_store import SQLiteStore, loads
from app.researcher_api.services.diagnostics_service import DiagnosticsService
from app.researcher_api.services.run_data_service import RunDataService


class AdminExportService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.run_data_service = RunDataService(store)
        self.diagnostics_service = DiagnosticsService(store)

    def export_run(self, run_id: str) -> dict[str, Any]:
        run_data = self.run_data_service.load_run_scoped_data(run_id)
        session_payload = run_data.session_payload
        session_ids = run_data.session_ids

        if not session_ids:
            return {
                "run_id": run_id,
                "export_state": "empty",
                "message": "No sessions for this run yet. Start participant sessions before exporting.",
                "raw_event_log_jsonl": "",
                "trial_summary_csv": "",
                "block_questionnaire_csv": "",
                "session_summary_csv": "",
                "session_summary_json": [],
                "trial_level_csv": "",
                "participant_summary_csv": "",
                "mixed_effects_ready_csv": "",
                "pilot_summary_md": "",
                "available_outputs": {
                    "raw_event_log_jsonl": False,
                    "trial_summary_csv": False,
                    "block_questionnaire_csv": False,
                    "session_summary_csv": False,
                    "trial_level_csv": False,
                    "participant_summary_csv": False,
                    "mixed_effects_ready_csv": False,
                    "pilot_summary_md": False,
                },
                "warnings": ["No sessions linked to this run yet"],
            }

        raw_event_log_jsonl = "\n".join(
            json.dumps(
                {
                    "event_id": row["event_id"],
                    "session_id": row["session_id"],
                    "block_id": row["block_id"],
                    "trial_id": row["trial_id"],
                    "timestamp": row["timestamp"],
                    "event_type": row["event_type"],
                    "payload": loads(row["payload_json"]),
                },
                sort_keys=True,
            )
            for row in run_data.event_rows
        )

        trial_summary_csv = _to_csv(run_data.trial_summary_rows)

        session_summary_rows = []
        for row in session_payload["sessions"]:
            session_row = dict(row)
            session_row["run_id"] = run_id
            session_summary_rows.append(session_row)

        warnings: list[str] = []
        trial_level_rows: list[dict[str, Any]] = []
        participant_rows: list[dict[str, Any]] = []
        mixed_rows: list[dict[str, Any]] = []
        report_md = ""
        diagnostics = self.diagnostics_service.get_run_diagnostics(run_id)
        if run_data.trial_summary_rows:
            trial_level_rows, derive_warnings = derive_trial_level_rows(run_data.trial_summary_rows)
            warnings.extend(derive_warnings)
            exclusion_rows = compute_exclusion_flags(trial_level_rows, session_summary_rows)
            participant_rows = build_participant_summary(trial_level_rows, exclusion_rows, run_data.questionnaire_rows)
            mixed_rows = build_mixed_effects_ready(trial_level_rows, participant_rows)
            report_md = build_report(
                trial_level_rows,
                participant_rows,
                exclusion_rows,
                session_summary_rows,
                diagnostics,
            )
        else:
            warnings.append("No trial summaries available; derived analysis-ready outputs are unavailable")

        return {
            "run_id": run_id,
            "export_state": "available",
            "message": "Run exports are available.",
            "raw_event_log_jsonl": raw_event_log_jsonl,
            "trial_summary_csv": trial_summary_csv,
            "block_questionnaire_csv": _to_csv(run_data.questionnaire_rows),
            "session_summary_csv": _to_csv(session_summary_rows),
            "session_summary_json": session_summary_rows,
            "trial_level_csv": _to_csv(trial_level_rows),
            "participant_summary_csv": _to_csv(participant_rows),
            "mixed_effects_ready_csv": _to_csv(mixed_rows),
            "pilot_summary_md": report_md,
            "available_outputs": {
                "raw_event_log_jsonl": bool(raw_event_log_jsonl),
                "trial_summary_csv": bool(trial_summary_csv),
                "block_questionnaire_csv": bool(run_data.questionnaire_rows),
                "session_summary_csv": bool(session_summary_rows),
                "trial_level_csv": bool(trial_level_rows),
                "participant_summary_csv": bool(participant_rows),
                "mixed_effects_ready_csv": bool(mixed_rows),
                "pilot_summary_md": bool(report_md),
            },
            "warnings": warnings,
        }


def _to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
