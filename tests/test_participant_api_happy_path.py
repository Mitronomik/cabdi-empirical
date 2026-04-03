from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app
from app.researcher_api.main import create_app as create_researcher_app


def _make_client(tmp_path):
    db_path = tmp_path / "pilot_api.sqlite3"
    app = create_app(str(db_path))
    return TestClient(app)


def _bootstrap_run(tmp_path) -> str:
    db_path = str(tmp_path / "pilot_api.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
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
    run = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "participant test run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    return run.json()["run_id"]


def test_health_endpoint(tmp_path):
    client = _make_client(tmp_path)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_session_flow_happy_path_with_exports(tmp_path):
    client = _make_client(tmp_path)
    run_id = _bootstrap_run(tmp_path)

    create_res = client.post(
        "/api/v1/sessions",
        json={"experiment_id": "toy_v1", "participant_id": "p_001", "run_id": run_id},
    )
    assert create_res.status_code == 200
    session_id = create_res.json()["session_id"]

    start_res = client.post(f"/api/v1/sessions/{session_id}/start")
    assert start_res.status_code == 200

    submitted = 0
    questionnaire_submitted = set()

    while True:
        next_res = client.get(f"/api/v1/sessions/{session_id}/next-trial")
        assert next_res.status_code in {200, 409}
        if next_res.status_code == 409:
            block_id = next_res.json()["detail"]["block_id"]
            q_res = client.post(
                f"/api/v1/sessions/{session_id}/blocks/{block_id}/questionnaire",
                json={"burden": 25, "trust": 50, "usefulness": 75},
            )
            assert q_res.status_code == 200
            questionnaire_submitted.add(block_id)
            continue

        payload = next_res.json()
        if payload.get("status") == "completed":
            break

        submit_res = client.post(
            f"/api/v1/sessions/{session_id}/trials/{payload['trial_id']}/submit",
            json={
                "human_response": payload["stimulus"]["true_label"],
                "reaction_time_ms": 1200,
                "self_confidence": 61,
                "reason_clicked": True,
                "evidence_opened": False,
                "verification_completed": True,
            },
        )
        assert submit_res.status_code == 200
        submitted += 1

    assert submitted == 54
    assert questionnaire_submitted == {"block_1", "block_2", "block_3"}

    export_res = client.get(f"/api/v1/exports/sessions/{session_id}")
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert "raw_event_log_jsonl" in export_data
    assert "trial_summary_csv" in export_data
    assert "block_questionnaire_csv" in export_data
    assert export_data["participant_session_summary"]["n_trial_summaries"] == 54
    assert export_data["participant_session_summary"]["language"] == "en"


def test_session_creation_stores_language_metadata(tmp_path):
    client = _make_client(tmp_path)
    run_id = _bootstrap_run(tmp_path)

    create_res = client.post(
        "/api/v1/sessions",
        json={"experiment_id": "toy_v1", "participant_id": "p_ru", "run_id": run_id, "language": "ru"},
    )
    assert create_res.status_code == 200
    session_id = create_res.json()["session_id"]

    export_res = client.get(f"/api/v1/exports/sessions/{session_id}")
    assert export_res.status_code == 200
    assert export_res.json()["participant_session_summary"]["language"] == "ru"


def test_session_creation_requires_run_id(tmp_path):
    client = _make_client(tmp_path)
    create_res = client.post(
        "/api/v1/sessions",
        json={"experiment_id": "toy_v1", "participant_id": "p_missing_run"},
    )
    assert create_res.status_code == 422
