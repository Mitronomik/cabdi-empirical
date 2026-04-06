from __future__ import annotations

from fastapi.testclient import TestClient

from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _upload_stimulus(client: TestClient) -> str:
    payload = (
        '{"stimulus_id":"s1","task_family":"scam_detection","content_type":"text","payload":{"title":"Case 1","body":"a"},'
        '"true_label":"scam","difficulty_prior":"low","model_prediction":"scam","model_confidence":"high",'
        '"model_correct":true,"eligible_sets":["demo"]}\n'
    )
    res = client.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", payload, "application/json")},
        data={"name": "set1", "source_format": "jsonl"},
    )
    assert res.status_code == 200
    return str(res.json()["stimulus_set_id"])


def test_invite_url_is_returned_and_derived_from_public_slug(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PILOT_PARTICIPANT_BASE_URL", "http://participant.local:5173/")
    client = TestClient(create_researcher_app(str(tmp_path / "pilot.sqlite3")))
    _login_researcher(client)
    stimulus_set_id = _upload_stimulus(client)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "Invite Link Run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 3},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    assert create.status_code == 200
    run_id = str(create.json()["run_id"])
    assert create.json()["public_slug"] == "invite-link-run"
    assert create.json()["invite_url"] == "http://participant.local:5173/join/invite-link-run"

    detail = client.get(f"/admin/api/v1/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["invite_url"] == "http://participant.local:5173/join/invite-link-run"


def test_run_states_expose_launchability_consistently(tmp_path) -> None:
    client = TestClient(create_researcher_app(str(tmp_path / "pilot.sqlite3")))
    _login_researcher(client)
    stimulus_set_id = _upload_stimulus(client)
    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "Launchability Run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 3},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    run_id = str(create.json()["run_id"])

    draft = client.get(f"/admin/api/v1/runs/{run_id}")
    assert draft.json()["run_status"] == "draft"
    assert draft.json()["launchable"] is False
    assert draft.json()["launchability_state"] == "not_launchable"

    active = client.post(f"/admin/api/v1/runs/{run_id}/activate")
    assert active.status_code == 200
    assert active.json()["run_status"] == "active"
    assert active.json()["launchable"] is True
    assert active.json()["launchability_state"] == "launchable"

    paused = client.post(f"/admin/api/v1/runs/{run_id}/pause")
    assert paused.status_code == 200
    assert paused.json()["run_status"] == "paused"
    assert paused.json()["launchable"] is False
    assert paused.json()["launchability_state"] == "not_launchable"
