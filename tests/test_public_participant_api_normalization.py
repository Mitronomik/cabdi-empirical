from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _bootstrap_run(tmp_path) -> tuple[TestClient, str]:
    db_path = str(tmp_path / "pilot_api.sqlite3")
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
            "run_name": "public-api-normalization",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test", "n_blocks": 1},
            "stimulus_set_ids": [upload.json()["stimulus_set_id"]],
        },
    )
    run_id = run.json()["run_id"]
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200
    participant = TestClient(create_participant_app(db_path))
    return participant, run.json()["public_slug"]


def test_canonical_public_routes_cover_session_lifecycle(tmp_path) -> None:
    participant, run_slug = _bootstrap_run(tmp_path)

    created = participant.post(f"/api/v1/public/runs/{run_slug}/sessions", json={"language": "en"})
    assert created.status_code == 200
    created_body = created.json()
    session_id = created_body["session_id"]
    resume_token = created_body["resume_token"]

    assert participant.post(f"/api/v1/public/sessions/{session_id}/start").status_code == 200
    progress = participant.get(f"/api/v1/public/sessions/{session_id}/progress")
    assert progress.status_code == 200
    assert progress.json()["session_id"] == session_id

    resume_info = participant.post(
        f"/api/v1/public/runs/{run_slug}/resume-info",
        json={"resume_token": resume_token},
    )
    assert resume_info.status_code == 200
    assert resume_info.json()["resume_status"] == "resumable"

    resumed = participant.post(
        f"/api/v1/public/runs/{run_slug}/resume",
        json={"resume_token": resume_token},
    )
    assert resumed.status_code == 200
    assert resumed.json()["session_id"] == session_id


def test_legacy_session_alias_routes_still_work(tmp_path) -> None:
    participant, run_slug = _bootstrap_run(tmp_path)

    created = participant.post("/api/v1/sessions", json={"run_slug": run_slug, "language": "en"})
    assert created.status_code == 200
    assert created.headers["Deprecation"] == "true"
    session_id = created.json()["session_id"]
    start = participant.post(f"/api/v1/sessions/{session_id}/start")
    assert start.status_code == 200
    assert start.headers["Deprecation"] == "true"
    next_trial = participant.get(f"/api/v1/sessions/{session_id}/next-trial")
    assert next_trial.status_code == 200
    assert next_trial.headers["Deprecation"] == "true"


def test_openapi_marks_legacy_alias_routes_as_deprecated(tmp_path) -> None:
    participant, _ = _bootstrap_run(tmp_path)

    schema = participant.get("/openapi.json").json()
    paths = schema["paths"]
    assert paths["/api/v1/public/runs/{run_slug}/sessions"]["post"].get("deprecated") is not True
    assert paths["/api/v1/public/sessions/{session_id}/next-trial"]["get"].get("deprecated") is not True
    assert paths["/api/v1/sessions"]["post"]["deprecated"] is True
    assert paths["/api/v1/sessions/{session_id}/start"]["post"]["deprecated"] is True
    assert paths["/api/v1/sessions/{session_id}/next-trial"]["get"]["deprecated"] is True
