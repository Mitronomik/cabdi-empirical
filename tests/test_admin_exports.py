from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _bootstrap_run(researcher: TestClient) -> dict[str, str]:
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
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "run export",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 3},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    activate = researcher.post(f"/admin/api/v1/runs/{run_res.json()['run_id']}/activate")
    assert activate.status_code == 200
    return {"run_id": run_res.json()["run_id"], "run_slug": run_res.json()["public_slug"]}


def test_run_exports_include_expected_sections(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    participant = TestClient(create_participant_app(db_path))

    run_info = _bootstrap_run(researcher)
    create_session = participant.post(
        "/api/v1/sessions",
        json={"participant_id": "p_export_1", "run_slug": run_info["run_slug"], "language": "ru"},
    )
    assert create_session.status_code == 200

    exports_res = researcher.get(f"/admin/api/v1/runs/{run_info['run_id']}/exports")
    assert exports_res.status_code == 200
    body = exports_res.json()
    assert "raw_event_log_jsonl" in body
    assert "trial_summary_csv" in body
    assert "block_questionnaire_csv" in body
    assert "session_summary_json" in body
    assert "trial_level_csv" in body
    assert "participant_summary_csv" in body
    assert "mixed_effects_ready_csv" in body
    assert "pilot_summary_md" in body
    assert body["export_state"] == "available"
    assert "available_outputs" in body
    assert body["available_outputs"]["session_summary_csv"] is True
    assert body["available_outputs"]["trial_level_csv"] is False
    assert body["session_summary_json"][0]["language"] == "ru"
    assert "No trial summaries available" in body["warnings"][0]


def test_run_exports_include_analysis_ready_outputs_when_trial_data_exists(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    participant = TestClient(create_participant_app(db_path))

    run_info = _bootstrap_run(researcher)
    create_session = participant.post(
        "/api/v1/sessions",
        json={"participant_id": "p_export_full", "run_slug": run_info["run_slug"], "language": "en"},
    )
    assert create_session.status_code == 200
    session_id = create_session.json()["session_id"]
    assert participant.post(f"/api/v1/sessions/{session_id}/start").status_code == 200
    next_trial = participant.get(f"/api/v1/sessions/{session_id}/next-trial")
    trial_payload = next_trial.json()
    trial_id = trial_payload["trial_id"]
    submit = participant.post(
        f"/api/v1/sessions/{session_id}/trials/{trial_id}/submit",
        json={
            "human_response": trial_payload["stimulus"]["model_prediction"],
            "self_confidence": 50,
            "reaction_time_ms": 1200,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
        },
    )
    assert submit.status_code == 200

    exports_res = researcher.get(f"/admin/api/v1/runs/{run_info['run_id']}/exports")
    assert exports_res.status_code == 200
    body = exports_res.json()
    assert body["available_outputs"]["trial_level_csv"] is True
    assert body["available_outputs"]["participant_summary_csv"] is True
    assert body["available_outputs"]["mixed_effects_ready_csv"] is True
    assert body["available_outputs"]["pilot_summary_md"] is True

    trial_summary_rows = list(csv.DictReader(io.StringIO(body["trial_summary_csv"])))
    assert trial_summary_rows
    assert trial_summary_rows[0]["run_id"] == run_info["run_id"]
    assert trial_summary_rows[0]["session_id"] == session_id
    assert trial_summary_rows[0]["trial_id"] == trial_id

    trial_level_rows = list(csv.DictReader(io.StringIO(body["trial_level_csv"])))
    assert trial_level_rows
    assert trial_level_rows[0]["session_id"] == session_id
