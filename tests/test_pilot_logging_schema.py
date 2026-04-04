from __future__ import annotations

import csv
import io
import json

from fastapi.testclient import TestClient

from app.participant_api.main import create_app
from app.researcher_api.main import create_app as create_researcher_app
from packages.logging_schema.pilot_logs import TrialEventLog, TrialSummaryLog


def _bootstrap_run(tmp_path) -> str:
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    login = researcher.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert login.status_code == 200
    payload = (
        '{"stimulus_id":"s1","task_family":"scam_detection","content_type":"text","payload":{"title":"Case 1","body":"a"},'
        '"true_label":"scam","difficulty_prior":"low","model_prediction":"scam","model_confidence":"high",'
        '"model_correct":true,"eligible_sets":["demo"]}\n'
    )
    upload = researcher.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", payload, "application/json")},
        data={"name": "set1", "source_format": "jsonl"},
    )
    stimulus_set_id = upload.json()["stimulus_set_id"]
    run = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "logging test run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    activate = researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate")
    assert activate.status_code == 200
    return run.json()["public_slug"]


def test_trial_event_log_accepts_supported_event_types():
    event = TrialEventLog(
        event_id="evt_1",
        session_id="sess_1",
        block_id="block_1",
        trial_id="trial_1",
        timestamp="2026-01-01T00:00:00",
        event_type="trial_started",
        payload={"condition": "static_help"},
    )
    encoded = event.to_dict()
    decoded = TrialEventLog.from_dict(encoded)
    assert decoded.event_type == "trial_started"


def test_trial_summary_log_completeness_and_roundtrip():
    summary = TrialSummaryLog(
        participant_id="p1",
        session_id="s1",
        experiment_id="pilot_scam_not_scam_v1",
        condition="monotone_help",
        stimulus_id="sns_001",
        task_family="scam_not_scam",
        true_label="scam",
        human_response="scam",
        correct_or_not=True,
        model_prediction="scam",
        model_confidence="high",
        model_correct_or_not=True,
        risk_bucket="extreme",
        shown_help_level="high",
        shown_verification_level="forced",
        shown_components=["prediction", "confidence", "rationale"],
        accepted_model_advice=True,
        overrode_model=False,
        verification_required=True,
        verification_completed=True,
        reason_clicked=True,
        evidence_opened=False,
        reaction_time_ms=1800,
        self_confidence=76,
    )

    data = summary.to_dict()
    restored = TrialSummaryLog.from_dict(data)
    assert restored.correct_or_not is True


def test_completed_trials_have_summary_rows_and_required_fields(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    run_slug = _bootstrap_run(tmp_path)
    client = TestClient(create_app(db_path))
    created = client.post("/api/v1/sessions", json={"run_slug": run_slug}).json()
    session_id = created["session_id"]
    client.post(f"/api/v1/sessions/{session_id}/start")

    trial = client.get(f"/api/v1/sessions/{session_id}/next-trial").json()
    client.post(
        f"/api/v1/sessions/{session_id}/trials/{trial['trial_id']}/submit",
        json={
            "human_response": trial["stimulus"]["true_label"],
            "reaction_time_ms": 999,
            "self_confidence": 55,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
            "event_trace": [{"event_type": "response_selected", "payload": {"source": "test"}}],
        },
    )

    exported = client.get(f"/api/v1/exports/sessions/{session_id}").json()
    rows = list(csv.DictReader(io.StringIO(exported["trial_summary_csv"])))
    assert len(rows) == 1
    required = {"session_id", "stimulus_id", "human_response", "risk_bucket", "shown_components"}
    assert required.issubset(rows[0].keys())

    events = [json.loads(line) for line in exported["raw_event_log_jsonl"].splitlines() if line.strip()]
    assert any(evt["event_type"] == "trial_completed" for evt in events)
