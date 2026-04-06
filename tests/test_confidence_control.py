from __future__ import annotations

import csv

from fastapi.testclient import TestClient

from analysis.pilot.exclusions import compute_exclusion_flags
from app.participant_api.main import create_app
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _bootstrap_run(tmp_path) -> str:
    db_path = str(tmp_path / "pilot_confidence.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    payload = (
        '{"stimulus_id":"s1","task_family":"scam_detection","content_type":"text","payload":{"title":"Case","body":"a"},'
        '"true_label":"scam","difficulty_prior":"low","model_prediction":"scam","model_confidence":"high",'
        '"model_correct":true,"eligible_sets":["demo"]}\n'
    )
    upload = researcher.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", payload, "application/json")},
        data={"name": "set1", "source_format": "jsonl"},
    )
    run = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "confidence run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [upload.json()["stimulus_set_id"]],
        },
    )
    researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate")
    return run.json()["public_slug"]


def test_confidence_submission_requires_ordinal_1_to_4_and_exports_preserve_value(tmp_path):
    client = TestClient(create_app(str(tmp_path / "pilot_confidence.sqlite3")))
    run_slug = _bootstrap_run(tmp_path)

    created = client.post("/api/v1/sessions", json={"run_slug": run_slug})
    session_id = created.json()["session_id"]
    client.post(f"/api/v1/sessions/{session_id}/start")
    trial = client.get(f"/api/v1/sessions/{session_id}/next-trial").json()
    assert trial["self_confidence_scale"] == {"type": "4_point", "min": 1, "max": 4, "step": 1}

    invalid = client.post(
        f"/api/v1/sessions/{session_id}/trials/{trial['trial_id']}/submit",
        json={
            "human_response": trial["stimulus"]["true_label"],
            "reaction_time_ms": 600,
            "self_confidence": 5,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
        },
    )
    assert invalid.status_code == 422

    valid = client.post(
        f"/api/v1/sessions/{session_id}/trials/{trial['trial_id']}/submit",
        json={
            "human_response": trial["stimulus"]["true_label"],
            "reaction_time_ms": 600,
            "self_confidence": 4,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
        },
    )
    assert valid.status_code == 200

    export = client.get(f"/api/v1/exports/sessions/{session_id}")
    rows = list(csv.DictReader(export.json()["trial_summary_csv"].splitlines()))
    assert rows[0]["self_confidence"] == "4"


def test_missing_confidence_is_flagged_in_exclusions():
    flags = compute_exclusion_flags(
        trial_level_rows=[
            {
                "session_id": "s1",
                "participant_id": "p1",
                "trial_id": "t1",
                "stimulus_id": "st1",
                "reaction_time_ms": "500",
                "confidence": "",
                "followed_model": "1",
                "correct": "1",
            }
        ]
    )
    assert flags[0]["missing_confidence_reports"] is True

