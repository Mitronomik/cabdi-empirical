"""Reproducible dry-run / QA harness for toy human-pilot flow (PR-7)."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from random import Random
from typing import Any

from fastapi.testclient import TestClient

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.participant_api.persistence.sqlite_store import SQLiteStore
from app.participant_api.main import create_app as create_participant_app
from app.researcher_api.services.diagnostics_service import DiagnosticsService
from app.researcher_api.services.export_service import AdminExportService
from app.researcher_api.services.run_service import RunService
from app.researcher_api.services.stimulus_service import StimulusService
from experiments.helpers.fake_participant_simulator import PROFILE_LIBRARY, decide_trial_submission
from experiments.run_pilot_analysis import main as run_pilot_analysis_main

REQUIRED_EVENT_FIELDS = {"event_id", "session_id", "block_id", "trial_id", "timestamp", "event_type", "payload"}
REQUIRED_TRIAL_SUMMARY_FIELDS = {
    "participant_id",
    "session_id",
    "experiment_id",
    "condition",
    "stimulus_id",
    "human_response",
    "true_label",
    "model_prediction",
    "risk_bucket",
    "reaction_time_ms",
    "self_confidence",
}


def _load_json_config(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _assign_profiles(profile_mix: dict[str, int], n_sessions: int, rng: Random) -> list[str]:
    assigned = []
    for profile_name, count in profile_mix.items():
        assigned.extend([profile_name] * int(count))
    if len(assigned) < n_sessions:
        fallback = ["mostly_compliant", "fast_noisy", "cautious_verifier", "advice_follower", "low_conf_override"]
        while len(assigned) < n_sessions:
            assigned.append(fallback[len(assigned) % len(fallback)])
    assigned = assigned[:n_sessions]
    rng.shuffle(assigned)
    return assigned


def _create_run(
    stimulus_service: StimulusService,
    run_service: RunService,
    stimulus_path: Path,
    run_name: str,
    experiment_id: str,
    task_family: str,
) -> str:
    upload = stimulus_service.upload_stimulus_set(
        name=f"dry_run_{run_name}",
        content=stimulus_path.read_bytes(),
        source_format="jsonl",
    )
    if not upload.get("ok", False):
        raise ValueError(f"Dry-run stimulus upload failed: {upload.get('errors', [])}")

    run = run_service.create_run(
        run_name=run_name,
        experiment_id=experiment_id,
        task_family=task_family,
        config={"mode": "dry_run"},
        stimulus_set_ids=[str(upload["stimulus_set_id"])],
        notes="PR-7 dry-run QA harness",
    )
    activated = run_service.activate_run(str(run["run_id"]))
    if activated["status"] != "active":
        raise ValueError(f"Dry-run failed to activate run: {run['run_id']}")
    return str(run["run_id"])


def _simulate_session(participant_client: TestClient, session_id: str, rng: Random, profile_name: str) -> dict[str, Any]:
    profile = PROFILE_LIBRARY[profile_name]
    participant_client.post(f"/api/v1/sessions/{session_id}/start").raise_for_status()

    submitted_trials = 0
    questionnaires = set()
    condition_counts = Counter()

    while True:
        next_res = participant_client.get(f"/api/v1/sessions/{session_id}/next-trial")
        if next_res.status_code == 409:
            block_id = next_res.json()["detail"]["block_id"]
            participant_client.post(
                f"/api/v1/sessions/{session_id}/blocks/{block_id}/questionnaire",
                json={
                    "burden": rng.randint(20, 70),
                    "trust": rng.randint(20, 80),
                    "usefulness": rng.randint(20, 85),
                },
            ).raise_for_status()
            questionnaires.add(block_id)
            continue

        next_res.raise_for_status()
        payload = next_res.json()
        if payload.get("status") in {"awaiting_final_submit", "finalized", "completed"}:
            if payload.get("status") == "awaiting_final_submit":
                participant_client.post(f"/api/v1/sessions/{session_id}/final-submit").raise_for_status()
            break

        condition_counts[payload["policy_decision"]["condition"]] += 1
        submission = decide_trial_submission(trial_payload=payload, profile=profile, rng=rng)
        participant_client.post(
            f"/api/v1/sessions/{session_id}/trials/{payload['trial_id']}/submit",
            json=submission,
        ).raise_for_status()
        submitted_trials += 1

    return {
        "session_id": session_id,
        "profile": profile_name,
        "submitted_trials": submitted_trials,
        "questionnaires_submitted": sorted(questionnaires),
        "condition_counts": dict(condition_counts),
    }


def _run_analysis_pipeline(
    *,
    trial_summary_csv: Path,
    event_log_jsonl: Path,
    session_summary_csv: Path,
    block_questionnaire_csv: Path,
    output_dir: Path,
    diagnostics_json: Path,
) -> None:
    import sys

    argv_backup = list(sys.argv)
    sys.argv = [
        "run_pilot_analysis",
        "--trial-summary-csv",
        str(trial_summary_csv),
        "--event-log-jsonl",
        str(event_log_jsonl),
        "--session-summary-csv",
        str(session_summary_csv),
        "--block-questionnaire-csv",
        str(block_questionnaire_csv),
        "--diagnostics-json",
        str(diagnostics_json),
        "--output-dir",
        str(output_dir),
    ]
    try:
        run_pilot_analysis_main()
    finally:
        sys.argv = argv_backup


def _integrity_checks(output_dir: Path, db_path: Path) -> dict[str, Any]:
    checks: dict[str, Any] = {"errors": [], "warnings": []}

    trial_level_rows = _read_csv_rows(output_dir / "trial_level.csv")
    participant_rows = _read_csv_rows(output_dir / "participant_summary.csv")
    mixed_rows = _read_csv_rows(output_dir / "mixed_effects_ready.csv")

    if not trial_level_rows:
        checks["errors"].append("analysis trial_level.csv is empty")
    if not participant_rows:
        checks["errors"].append("analysis participant_summary.csv is empty")
    if not mixed_rows:
        checks["errors"].append("analysis mixed_effects_ready.csv is empty")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    with conn:
        completed_trials = conn.execute("SELECT COUNT(*) AS n FROM session_trials WHERE status = 'completed'").fetchone()["n"]
        summary_trials = conn.execute("SELECT COUNT(*) AS n FROM trial_summary_logs").fetchone()["n"]
        completed_sessions = conn.execute(
            "SELECT COUNT(*) AS n FROM participant_sessions WHERE status IN ('finalized', 'completed')"
        ).fetchone()["n"]
        completed_with_time = conn.execute(
            "SELECT COUNT(*) AS n FROM participant_sessions WHERE status IN ('finalized', 'completed') AND completed_at IS NOT NULL"
        ).fetchone()["n"]

        if completed_trials != summary_trials:
            checks["errors"].append(f"trial summary mismatch: completed_trials={completed_trials}, summary_rows={summary_trials}")
        if completed_sessions != completed_with_time:
            checks["errors"].append("completed sessions missing completed_at timestamps")

        events = [dict(row) for row in conn.execute("SELECT * FROM trial_event_logs")]
        missing_event_fields = 0
        for row in events:
            if any(row.get(field) in (None, "") for field in REQUIRED_EVENT_FIELDS if field != "payload"):
                missing_event_fields += 1
        if missing_event_fields:
            checks["errors"].append(f"event rows missing required fields: {missing_event_fields}")

        summary_rows = [json.loads(row["summary_json"]) for row in conn.execute("SELECT summary_json FROM trial_summary_logs")]
        missing_summary_fields = 0
        for row in summary_rows:
            if any(row.get(field) in (None, "") for field in REQUIRED_TRIAL_SUMMARY_FIELDS):
                missing_summary_fields += 1
        if missing_summary_fields:
            checks["errors"].append(f"trial summaries missing required fields: {missing_summary_fields}")

        policy_rows = [
            dict(row)
            for row in conn.execute(
                "SELECT trial_id, risk_bucket, policy_decision_json FROM session_trials WHERE status='completed'"
            )
        ]
        mismatched_policy_risk = 0
        for row in policy_rows:
            if not row["policy_decision_json"]:
                mismatched_policy_risk += 1
                continue
            decision = json.loads(row["policy_decision_json"])
            if str(decision.get("risk_bucket", "")) != str(row["risk_bucket"]):
                mismatched_policy_risk += 1
        if mismatched_policy_risk:
            checks["errors"].append(f"policy decisions not reconstructable for {mismatched_policy_risk} completed trials")

    checks["counts"] = {
        "completed_trials": int(completed_trials),
        "trial_summaries": int(summary_trials),
        "completed_sessions": int(completed_sessions),
    }
    return checks


def _build_dry_run_report(
    *,
    report_path: Path,
    config: dict[str, Any],
    session_runs: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    checks: dict[str, Any],
    analysis_dir: Path,
) -> None:
    total_trials = sum(int(s["submitted_trials"]) for s in session_runs)
    condition_counts = Counter()
    for row in session_runs:
        condition_counts.update(row["condition_counts"])

    lines = [
        "# Toy Pilot Dry-Run QA Report",
        "",
        "This report documents a synthetic dry-run QA execution for the toy human-pilot flow.",
        "It supports MVP readiness checks only and does **not** substitute for human-participant data.",
        "",
        "## Run configuration",
        f"- Seed: `{config['seed']}`",
        f"- Sessions simulated: `{len(session_runs)}`",
        f"- Profiles: `{config['profile_mix']}`",
        "- Simulated flow: consent -> practice -> main blocks -> block questionnaires -> completion.",
        "",
        "## Lifecycle + logging integrity",
        f"- Completed sessions: `{checks['counts']['completed_sessions']}`",
        f"- Completed trials: `{checks['counts']['completed_trials']}`",
        f"- Trial summaries: `{checks['counts']['trial_summaries']}`",
        f"- Integrity errors: `{len(checks['errors'])}`",
        f"- Integrity warnings: `{len(checks['warnings'])}`",
    ]

    if checks["errors"]:
        lines.append("- Errors:")
        lines.extend([f"  - {item}" for item in checks["errors"]])

    lines.extend(
        [
            "",
            "## Condition/budget diagnostics",
            f"- Per-condition trial counts: `{dict(condition_counts)}`",
            f"- Budget tolerance flags: `{len(diagnostics.get('budget_tolerance_flags', []))}`",
            f"- Missing-field warnings: `{diagnostics.get('missing_core_fields_count', 0)}`",
            f"- Verification usage rate: `{diagnostics.get('verification_usage_rate', 0.0):.3f}`",
            f"- Reason click rate: `{diagnostics.get('reason_click_rate', 0.0):.3f}`",
            f"- Evidence open rate: `{diagnostics.get('evidence_open_rate', 0.0):.3f}`",
            "",
            "## Analysis pipeline outputs",
            f"- Exclusions summary source: `{analysis_dir / 'exclusion_flags.csv'}`",
            f"- Trial-level output: `{analysis_dir / 'trial_level.csv'}`",
            f"- Participant summary output: `{analysis_dir / 'participant_summary.csv'}`",
            f"- Mixed-effects-ready output: `{analysis_dir / 'mixed_effects_ready.csv'}`",
            "",
            "## Scientific guardrail note",
            "Dry-run completion and intact logging chain indicate implementation readiness for a toy pilot QA path.",
            "These outputs are not evidence about human cognition, physiology, or whole-framework real-world validity.",
        ]
    )

    _write_text(report_path, "\n".join(lines) + "\n")


def run_dry_run(config_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    config = _load_json_config(config_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    db_path = out_dir / "pilot_dry_run.sqlite3"
    if db_path.exists():
        db_path.unlink()

    rng = Random(int(config["seed"]))
    store = SQLiteStore(str(db_path))
    store.init_db()
    stimulus_service = StimulusService(store)
    run_service = RunService(store)
    diagnostics_service = DiagnosticsService(store)
    admin_export_service = AdminExportService(store)
    participant_client = TestClient(create_participant_app(str(db_path)))

    run_id = _create_run(
        stimulus_service,
        run_service,
        stimulus_path=Path(config["stimulus_path"]),
        run_name=config["run_name"],
        experiment_id=config["experiment_id"],
        task_family=config["task_family"],
    )
    run_slug = str(run_service.get_run(run_id)["public_slug"])

    session_runs = []
    profile_names = _assign_profiles(config["profile_mix"], int(config["n_sessions"]), rng)
    for session_idx in range(int(config["n_sessions"])):
        create_res = participant_client.post(
            "/api/v1/sessions",
            json={
                "run_slug": run_slug,
            },
        )
        create_res.raise_for_status()
        session_id = create_res.json()["session_id"]
        session_runs.append(_simulate_session(participant_client, session_id, rng, profile_names[session_idx]))

    exports_payload = admin_export_service.export_run(run_id)
    diagnostics = diagnostics_service.get_run_diagnostics(run_id)
    artifact_paths = {
        item["artifact_type"]: Path(exports_payload["artifact_root"]) / item["filename"]
        for item in exports_payload.get("artifacts", [])
    }

    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    event_log_path = raw_dir / "raw_event_log.jsonl"
    trial_summary_path = raw_dir / "trial_summary.csv"
    questionnaire_path = raw_dir / "block_questionnaire.csv"
    session_summary_path = raw_dir / "session_summary.csv"
    diagnostics_json_path = raw_dir / "diagnostics.json"

    _write_text(event_log_path, artifact_paths["raw_event_log_jsonl"].read_text(encoding="utf-8"))
    _write_text(trial_summary_path, artifact_paths["trial_summary_csv"].read_text(encoding="utf-8"))
    _write_text(questionnaire_path, artifact_paths["block_questionnaire_csv"].read_text(encoding="utf-8"))
    _write_text(session_summary_path, artifact_paths["session_summary_csv"].read_text(encoding="utf-8"))
    _write_json(diagnostics_json_path, diagnostics)

    analysis_dir = out_dir / "analysis"
    _run_analysis_pipeline(
        trial_summary_csv=trial_summary_path,
        event_log_jsonl=event_log_path,
        session_summary_csv=session_summary_path,
        block_questionnaire_csv=questionnaire_path,
        output_dir=analysis_dir,
        diagnostics_json=diagnostics_json_path,
    )

    checks = _integrity_checks(analysis_dir, db_path)

    report_path = out_dir / "pilot_dry_run.md"
    _build_dry_run_report(
        report_path=report_path,
        config=config,
        session_runs=session_runs,
        diagnostics=diagnostics,
        checks=checks,
        analysis_dir=analysis_dir,
    )

    summary = {
        "output_dir": str(out_dir),
        "run_id": run_id,
        "n_sessions": int(config["n_sessions"]),
        "integrity_errors": checks["errors"],
        "integrity_warnings": checks["warnings"],
        "report_path": str(report_path),
    }
    _write_json(out_dir / "dry_run_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run toy pilot dry-run / QA harness")
    parser.add_argument("--config", default="pilot/configs/dry_run_experiment.yaml")
    parser.add_argument("--output-dir", default="artifacts/pilot_dry_run")
    args = parser.parse_args()

    summary = run_dry_run(args.config, args.output_dir)
    if summary["integrity_errors"]:
        raise SystemExit(f"Dry-run completed with integrity errors: {summary['integrity_errors']}")


if __name__ == "__main__":
    main()
