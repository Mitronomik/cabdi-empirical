from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.researcher_api.main import create_app as create_researcher_app


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
    assert res.json()["ok"] is True
    assert res.json()["validation_status"] == "valid"
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
    assert create_run.json()["public_slug"] == "run-alpha"
    assert create_run.json()["ok"] is True
    assert create_run.json()["linked_stimulus_set_ids"] == [stimulus_set_id]
    assert create_run.json()["status"] == "draft"

    list_runs_res = researcher.get("/admin/api/v1/runs")
    assert list_runs_res.status_code == 200
    assert list_runs_res.json()[0]["run_id"] == run_id
    assert list_runs_res.json()[0]["status"] == "draft"
    assert list_runs_res.json()[0]["linked_stimulus_set_ids"] == [stimulus_set_id]
    assert list_runs_res.json()[0]["launchable"] is False

    list_stimuli_res = researcher.get("/admin/api/v1/stimuli")
    assert list_stimuli_res.status_code == 200
    assert list_stimuli_res.json()[0]["stimulus_set_id"] == stimulus_set_id
    assert list_stimuli_res.json()[0]["validation_status"] == "valid"
    assert list_stimuli_res.json()[0]["payload_schema_version"] == "stimulus_payload.v1"
    stimulus_detail = researcher.get(f"/admin/api/v1/stimuli/{stimulus_set_id}")
    assert stimulus_detail.status_code == 200
    assert len(stimulus_detail.json()["items"]) == 1
    assert stimulus_detail.json()["preview_rows"]

    defaults_res = researcher.get("/admin/api/v1/runs/defaults")
    assert defaults_res.status_code == 200
    assert defaults_res.json()["config_preset_id"] == "default_experiment"

    activate_res = researcher.post(f"/admin/api/v1/runs/{run_id}/activate")
    assert activate_res.status_code == 200
    assert activate_res.json()["status"] == "active"

    run_detail = researcher.get(f"/admin/api/v1/runs/{run_id}")
    assert run_detail.status_code == 200
    assert run_detail.json()["launchable"] is True

    session_res = participant.post(
        "/api/v1/sessions",
        json={"participant_id": "p_admin_1", "run_slug": create_run.json()["public_slug"], "language": "ru"},
    )
    assert session_res.status_code == 200

    sessions_res = researcher.get(f"/admin/api/v1/runs/{run_id}/sessions")
    assert sessions_res.status_code == 200
    sessions_body = sessions_res.json()
    assert sessions_body["counts"]["created"] >= 1
    assert sessions_body["sessions"][0]["language"] == "ru"
    assert sessions_body["run_status"] == "active"

    diagnostics_res = researcher.get(f"/admin/api/v1/runs/{run_id}/diagnostics")
    assert diagnostics_res.status_code == 200
    diagnostics_body = diagnostics_res.json()
    assert "missing_core_fields_count" in diagnostics_body
    assert "session_counts" in diagnostics_body


def test_run_lifecycle_transitions_and_invalid_transition_errors(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))

    stimulus_set_id = _upload_stimulus(researcher)
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "lifecycle run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 3},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    run_id = run_res.json()["run_id"]
    assert run_res.json()["status"] == "draft"

    pause_from_draft = researcher.post(f"/admin/api/v1/runs/{run_id}/pause")
    assert pause_from_draft.status_code == 400
    assert "Invalid run status transition" in pause_from_draft.json()["detail"]

    activate = researcher.post(f"/admin/api/v1/runs/{run_id}/activate")
    assert activate.status_code == 200
    assert activate.json()["status"] == "active"

    pause = researcher.post(f"/admin/api/v1/runs/{run_id}/pause")
    assert pause.status_code == 200
    assert pause.json()["status"] == "paused"

    activate_again = researcher.post(f"/admin/api/v1/runs/{run_id}/activate")
    assert activate_again.status_code == 200
    assert activate_again.json()["status"] == "active"

    close = researcher.post(f"/admin/api/v1/runs/{run_id}/close")
    assert close.status_code == 200
    assert close.json()["status"] == "closed"

    activate_closed = researcher.post(f"/admin/api/v1/runs/{run_id}/activate")
    assert activate_closed.status_code == 400
    assert "Invalid run status transition" in activate_closed.json()["detail"]


def test_closed_runs_remain_readable_for_diagnostics_and_exports(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_participant_app(db_path))

    stimulus_set_id = _upload_stimulus(researcher)
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "close-compatible run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 3},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    run_id = run_res.json()["run_id"]
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200
    assert participant.post(
        "/api/v1/sessions",
        json={"participant_id": "p_hist", "run_slug": run_res.json()["public_slug"]},
    ).status_code == 200
    closed = researcher.post(f"/admin/api/v1/runs/{run_id}/close")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    sessions = researcher.get(f"/admin/api/v1/runs/{run_id}/sessions")
    assert sessions.status_code == 200
    assert sessions.json()["run_status"] == "closed"
    diagnostics = researcher.get(f"/admin/api/v1/runs/{run_id}/diagnostics")
    assert diagnostics.status_code == 200
    exports = researcher.get(f"/admin/api/v1/runs/{run_id}/exports")
    assert exports.status_code == 200


def test_session_monitor_distinguishes_awaiting_final_submit_and_finalized(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_participant_app(db_path))

    stimulus_set_id = _upload_stimulus(researcher)
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "status split run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 3},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    run_id = run_res.json()["run_id"]
    run_slug = run_res.json()["public_slug"]
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200

    awaiting_session = participant.post(
        "/api/v1/sessions",
        json={"participant_id": "p_waiting", "run_slug": run_slug},
    ).json()["session_id"]
    finalized_session = participant.post(
        "/api/v1/sessions",
        json={"participant_id": "p_finalized", "run_slug": run_slug},
    ).json()["session_id"]

    participant.app.state.store.execute(
        "UPDATE participant_sessions SET status = 'awaiting_final_submit' WHERE session_id = ?",
        (awaiting_session,),
    )
    participant.app.state.store.execute(
        "UPDATE participant_sessions SET status = 'finalized', completed_at = '2026-01-01T00:00:00+00:00' WHERE session_id = ?",
        (finalized_session,),
    )

    sessions = researcher.get(f"/admin/api/v1/runs/{run_id}/sessions")
    assert sessions.status_code == 200
    counts = sessions.json()["counts"]
    assert counts["awaiting_final_submit"] == 1
    assert counts["finalized"] == 1
