from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.researcher_api.main import create_app as create_researcher_app


def _upload_stimulus(client: TestClient) -> str:
    payload = (
        '{"stimulus_id":"s1","task_family":"scam_detection","content_type":"text","payload":{"text":"a"},'
        '"true_label":"scam","difficulty_prior":"low","model_prediction":"scam","model_confidence":"high",'
        '"model_correct":true,"eligible_sets":["demo"]}\n'
    )
    res = client.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", payload, "application/json")},
        data={"name": "set1", "source_format": "jsonl"},
    )
    assert res.status_code == 200
    return res.json()["stimulus_set_id"]


def test_create_run_and_session_monitor_and_diagnostics(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_participant_app(db_path))

    stimulus_set_id = _upload_stimulus(researcher)

    create_run = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "run alpha",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 3},
            "stimulus_set_ids": [stimulus_set_id],
            "notes": "mvp",
        },
    )
    assert create_run.status_code == 200
    run_id = create_run.json()["run_id"]

    session_res = participant.post(
        "/api/v1/sessions",
        json={"experiment_id": "toy_v1", "participant_id": "p_admin_1", "run_id": run_id},
    )
    assert session_res.status_code == 200

    sessions_res = researcher.get(f"/admin/api/v1/runs/{run_id}/sessions")
    assert sessions_res.status_code == 200
    sessions_body = sessions_res.json()
    assert sessions_body["counts"]["created"] >= 1

    diagnostics_res = researcher.get(f"/admin/api/v1/runs/{run_id}/diagnostics")
    assert diagnostics_res.status_code == 200
    diagnostics_body = diagnostics_res.json()
    assert "missing_core_fields_count" in diagnostics_body
    assert "session_counts" in diagnostics_body
