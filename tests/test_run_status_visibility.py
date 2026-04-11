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


def test_run_statuses_render_consistently_in_researcher_ui_contract(tmp_path) -> None:
    client = TestClient(create_researcher_app(str(tmp_path / "pilot.sqlite3")))
    _login_researcher(client)
    stimulus_set_id = _upload_stimulus(client)
    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "Status Visibility Run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 1},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    run_id = str(create.json()["run_id"])

    expected = [
        ("draft", False, "not_launchable", False, True),
        ("active", True, "launchable", True, False),
        ("paused", False, "not_launchable", False, True),
        ("closed", False, "not_launchable", False, False),
    ]
    transitions = [None, "activate", "pause", "close"]

    for idx, (status, launchable, launchability_state, accepting_sessions_now, activation_ready) in enumerate(expected):
        if transitions[idx] is not None:
            path = f"/admin/api/v1/runs/{run_id}/{transitions[idx]}"
            payload = {"confirm_run_id": run_id} if transitions[idx] == "close" else None
            res = client.post(path, json=payload)
            assert res.status_code == 200

        detail = client.get(f"/admin/api/v1/runs/{run_id}")
        assert detail.status_code == 200
        detail_body = detail.json()

        listed = client.get("/admin/api/v1/runs")
        assert listed.status_code == 200
        listed_row = next(item for item in listed.json() if item["run_id"] == run_id)

        for body in (detail_body, listed_row):
            assert body["status"] == status
            assert body["run_status"] == status
            assert body["launchable"] is launchable
            assert body["launchability_state"] == launchability_state
            assert body["accepting_sessions_now"] is accepting_sessions_now
            assert body["activation_ready"] is activation_ready
            assert "ready_to_activate" not in body
            assert body["invite_url"].endswith("/join/status-visibility-run")

    closed_detail = client.get(f"/admin/api/v1/runs/{run_id}")
    assert closed_detail.status_code == 200
    assert closed_detail.json()["launchability_reason"] == "run is closed and does not accept new participant sessions"
