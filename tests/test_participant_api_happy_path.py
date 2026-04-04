from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.persistence.sqlite_store import dumps, loads

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
        '{"stimulus_id":"s1","task_family":"scam_detection","content_type":"text","payload":{"title":"Case","body":"a"},'
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
    activate = researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate")
    assert activate.status_code == 200
    return run.json()["public_slug"]


def _bootstrap_run_with_details(tmp_path) -> dict[str, str]:
    db_path = str(tmp_path / "pilot_api.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    payload = (
        '{"stimulus_id":"s1","task_family":"scam_detection","content_type":"text","payload":{"title":"Case","body":"original"},'
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
            "run_name": "snapshot run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    activate = researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate")
    assert activate.status_code == 200
    return {
        "run_id": run.json()["run_id"],
        "run_slug": run.json()["public_slug"],
        "stimulus_set_id": stimulus_set_id,
    }


def test_health_endpoint(tmp_path):
    client = _make_client(tmp_path)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_session_flow_happy_path_with_exports(tmp_path):
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)

    create_res = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_001", "run_slug": run_slug},
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
    run_slug = _bootstrap_run(tmp_path)

    create_res = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_ru", "run_slug": run_slug, "language": "ru"},
    )
    assert create_res.status_code == 200
    session_id = create_res.json()["session_id"]

    export_res = client.get(f"/api/v1/exports/sessions/{session_id}")
    assert export_res.status_code == 200
    assert export_res.json()["participant_session_summary"]["language"] == "ru"


def test_session_creation_by_unknown_run_slug_fails_clearly(tmp_path):
    client = _make_client(tmp_path)
    create_res = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_unknown", "run_slug": "missing-public-slug"},
    )
    assert create_res.status_code == 400
    assert "Unknown run_slug" in create_res.json()["detail"]


def test_session_creation_requires_run_reference(tmp_path):
    client = _make_client(tmp_path)
    create_res = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_missing_run"},
    )
    assert create_res.status_code == 422


def test_session_creation_does_not_accept_experiment_only_fallback(tmp_path):
    client = _make_client(tmp_path)
    create_res = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_legacy", "experiment_id": "toy_v1"},
    )
    assert create_res.status_code == 422


def test_session_creation_rejects_non_active_run(tmp_path):
    client = _make_client(tmp_path)
    db_path = str(tmp_path / "pilot_api.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
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
            "run_name": "draft run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [upload.json()["stimulus_set_id"]],
        },
    )
    create_res = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_non_active", "run_slug": run.json()["public_slug"]},
    )
    assert create_res.status_code == 400
    assert "status is draft" in create_res.json()["detail"]


def test_session_creation_rejects_paused_and_closed_runs(tmp_path):
    client = _make_client(tmp_path)
    db_path = str(tmp_path / "pilot_api.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
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
            "run_name": "status-checked run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [upload.json()["stimulus_set_id"]],
        },
    )
    run_id = run.json()["run_id"]
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/pause").status_code == 200

    paused_create = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_paused", "run_slug": run.json()["public_slug"]},
    )
    assert paused_create.status_code == 400
    assert "status is paused" in paused_create.json()["detail"]

    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/close").status_code == 200
    closed_create = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_closed", "run_slug": run.json()["public_slug"]},
    )
    assert closed_create.status_code == 400
    assert "status is closed" in closed_create.json()["detail"]


def test_session_creation_binds_session_to_resolved_run(tmp_path):
    client = _make_client(tmp_path)
    run_info = _bootstrap_run_with_details(tmp_path)
    create_res = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_bind", "run_slug": run_info["run_slug"]},
    )
    assert create_res.status_code == 200

    session_id = create_res.json()["session_id"]
    stored = client.app.state.store.fetchone(
        "SELECT run_id FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert stored is not None
    assert stored["run_id"] == run_info["run_id"]


def test_public_run_metadata_endpoint_returns_minimal_launch_info(tmp_path):
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)
    res = client.get(f"/api/v1/public/runs/{run_slug}")
    assert res.status_code == 200
    body = res.json()
    assert body["run_slug"] == run_slug
    assert body["launchable"] is True
    assert body["run_status"] == "active"
    assert "public_title" in body


def test_session_trials_are_frozen_snapshots_even_if_stimulus_set_changes(tmp_path):
    client = _make_client(tmp_path)
    run_info = _bootstrap_run_with_details(tmp_path)

    create_res = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_snapshot", "run_slug": run_info["run_slug"]},
    )
    assert create_res.status_code == 200
    session_id = create_res.json()["session_id"]

    rows = client.app.state.store.fetchall(
        "SELECT trial_id, stimulus_json FROM session_trials WHERE session_id = ? ORDER BY trial_id LIMIT 1",
        (session_id,),
    )
    assert rows
    frozen_before = loads(rows[0]["stimulus_json"])
    assert frozen_before["payload"]["body"] == "original"

    stim_row = client.app.state.store.fetchone(
        "SELECT items_json FROM researcher_stimulus_sets WHERE stimulus_set_id = ?",
        (run_info["stimulus_set_id"],),
    )
    assert stim_row is not None
    edited_items = loads(stim_row["items_json"])
    edited_items[0]["payload"]["body"] = "mutated"
    client.app.state.store.execute(
        "UPDATE researcher_stimulus_sets SET items_json = ? WHERE stimulus_set_id = ?",
        (dumps(edited_items), run_info["stimulus_set_id"]),
    )

    rows_after = client.app.state.store.fetchall(
        "SELECT trial_id, stimulus_json FROM session_trials WHERE session_id = ? ORDER BY trial_id LIMIT 1",
        (session_id,),
    )
    frozen_after = loads(rows_after[0]["stimulus_json"])
    assert frozen_after["payload"]["body"] == "original"
