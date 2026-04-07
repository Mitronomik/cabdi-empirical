from __future__ import annotations

from fastapi.testclient import TestClient

from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _upload_stimulus(client: TestClient, *, name: str, stimulus_id: str) -> str:
    payload = (
        f'{{"stimulus_id":"{stimulus_id}","task_family":"scam_detection","content_type":"text","payload":{{"title":"Case 1","body":"a"}},'
        '"true_label":"scam","difficulty_prior":"low","model_prediction":"scam","model_confidence":"high",'
        '"model_correct":true,"eligible_sets":["demo"]}\n'
    )
    res = client.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", payload, "application/json")},
        data={"name": name, "source_format": "jsonl"},
    )
    assert res.status_code == 200
    return str(res.json()["stimulus_set_id"])


def test_run_details_include_selected_banks_expected_trials_and_participant_link_data(tmp_path) -> None:
    client = TestClient(create_researcher_app(str(tmp_path / "pilot.sqlite3")))
    _login_researcher(client)
    main_set_id = _upload_stimulus(client, name="main-bank", stimulus_id="s_main")
    practice_set_id = _upload_stimulus(client, name="practice-bank", stimulus_id="s_practice")

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "details run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 3},
            "stimulus_set_ids": [main_set_id],
            "practice_stimulus_set_id": practice_set_id,
        },
    )
    assert create.status_code == 200
    run_id = str(create.json()["run_id"])

    details = client.get(f"/admin/api/v1/runs/{run_id}")
    assert details.status_code == 200
    body = details.json()

    assert body["public_slug"] == "details-run"
    assert body["invite_url"].endswith("/join/details-run")
    assert body["run_status"] == "draft"
    assert body["launchable"] is False
    assert body["launchability_state"] == "not_launchable"
    assert body["run_summary"]["practice_item_count"] == 1
    assert body["run_summary"]["main_item_count"] == 1
    assert body["run_summary"]["expected_trial_count"] == 2
    assert body["run_summary"]["selected_main_stimulus_set_ids"] == [main_set_id]
    assert len(body["run_summary"]["banks"]) == 1
    assert body["run_summary"]["banks"][0]["stimulus_set_id"] == main_set_id
    assert body["run_summary"]["practice_bank"]["stimulus_set_id"] == practice_set_id
