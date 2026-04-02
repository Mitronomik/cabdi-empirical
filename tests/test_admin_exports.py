from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.researcher_api.main import create_app as create_researcher_app


def _bootstrap_run(researcher: TestClient) -> str:
    payload = (
        '{"stimulus_id":"s1","task_family":"scam_detection","content_type":"text","payload":{"text":"a"},'
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
    return run_res.json()["run_id"]


def test_run_exports_include_expected_sections(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_participant_app(db_path))

    run_id = _bootstrap_run(researcher)
    create_session = participant.post(
        "/api/v1/sessions",
        json={"experiment_id": "toy_v1", "participant_id": "p_export_1", "run_id": run_id},
    )
    assert create_session.status_code == 200

    exports_res = researcher.get(f"/admin/api/v1/runs/{run_id}/exports")
    assert exports_res.status_code == 200
    body = exports_res.json()
    assert "raw_event_log_jsonl" in body
    assert "trial_summary_csv" in body
    assert "block_questionnaire_csv" in body
    assert "session_summary_json" in body
