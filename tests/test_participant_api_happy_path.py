from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.persistence.sqlite_store import dumps, loads

from app.participant_api.main import create_app
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _make_client(tmp_path):
    db_path = tmp_path / "pilot_api.sqlite3"
    app = create_app(str(db_path))
    return TestClient(app)


def _progress_session_to_awaiting_final_submit(client: TestClient, session_id: str) -> None:
    while True:
        next_res = client.get(f"/api/v1/sessions/{session_id}/next-trial")
        assert next_res.status_code in {200, 409}
        if next_res.status_code == 409:
            block_id = next_res.json()["detail"]["block_id"]
            q_res = client.post(
                f"/api/v1/sessions/{session_id}/blocks/{block_id}/questionnaire",
                json={"burden": 30, "trust": 40, "usefulness": 50},
            )
            assert q_res.status_code == 200
            continue
        body = next_res.json()
        if body.get("status") == "awaiting_final_submit":
            return
        submit_res = client.post(
            f"/api/v1/sessions/{session_id}/trials/{body['trial_id']}/submit",
            json={
                "human_response": body["stimulus"]["true_label"],
                "reaction_time_ms": 1000,
                "self_confidence": 70,
                "reason_clicked": False,
                "evidence_opened": False,
                "verification_completed": False,
            },
        )
        assert submit_res.status_code == 200


def _bootstrap_run(tmp_path) -> str:
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
    _login_researcher(researcher)
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
    assert create_res.json()["status"] == "created"

    start_res = client.post(f"/api/v1/sessions/{session_id}/start")
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "in_progress"

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
        if payload.get("status") in {"awaiting_final_submit", "finalized", "completed"}:
            assert payload["status"] == "awaiting_final_submit"
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

    expected_total = client.app.state.store.fetchone(
        "SELECT COUNT(*) AS n FROM session_trials WHERE session_id = ?",
        (session_id,),
    )["n"]
    assert submitted == expected_total
    assert questionnaire_submitted == {"block_1", "block_2", "block_3"}

    export_res = client.get(f"/api/v1/exports/sessions/{session_id}")
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert "raw_event_log_jsonl" in export_data
    assert "trial_summary_csv" in export_data
    assert "block_questionnaire_csv" in export_data
    assert export_data["participant_session_summary"]["n_trial_summaries"] == expected_total
    assert export_data["participant_session_summary"]["language"] == "en"
    assert export_data["participant_session_summary"]["status"] == "awaiting_final_submit"


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
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/close", json={"confirm_run_id": run_id}).status_code == 200
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


def test_progress_is_persisted_incrementally_and_not_finalized_on_trial_exhaustion(tmp_path):
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)

    create_res = client.post("/api/v1/sessions", json={"participant_id": "p_progress", "run_slug": run_slug})
    assert create_res.status_code == 200
    session_id = create_res.json()["session_id"]
    assert client.post(f"/api/v1/sessions/{session_id}/start").status_code == 200

    first_trial = client.get(f"/api/v1/sessions/{session_id}/next-trial")
    assert first_trial.status_code == 200
    payload = first_trial.json()
    submit = client.post(
        f"/api/v1/sessions/{session_id}/trials/{payload['trial_id']}/submit",
        json={
            "human_response": payload["stimulus"]["true_label"],
            "reaction_time_ms": 1000,
            "self_confidence": 70,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
        },
    )
    assert submit.status_code == 200

    row = client.app.state.store.fetchone(
        "SELECT current_block_index, current_trial_index, last_activity_at, status FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert row is not None
    assert row["current_trial_index"] >= 1
    assert row["last_activity_at"] is not None
    assert row["status"] == "in_progress"

    while True:
        next_res = client.get(f"/api/v1/sessions/{session_id}/next-trial")
        assert next_res.status_code in {200, 409}
        if next_res.status_code == 409:
            block_id = next_res.json()["detail"]["block_id"]
            q_res = client.post(
                f"/api/v1/sessions/{session_id}/blocks/{block_id}/questionnaire",
                json={"burden": 30, "trust": 40, "usefulness": 50},
            )
            assert q_res.status_code == 200
            continue
        body = next_res.json()
        if body.get("status") == "awaiting_final_submit":
            break
        client.post(
            f"/api/v1/sessions/{session_id}/trials/{body['trial_id']}/submit",
            json={
                "human_response": body["stimulus"]["true_label"],
                "reaction_time_ms": 1000,
                "self_confidence": 70,
                "reason_clicked": False,
                "evidence_opened": False,
                "verification_completed": False,
            },
        ).raise_for_status()

    final_row = client.app.state.store.fetchone(
        "SELECT status, completed_at FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert final_row is not None
    assert final_row["status"] == "awaiting_final_submit"
    assert final_row["completed_at"] is None


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


def test_final_submit_requires_eligible_session_and_finalizes_explicitly(tmp_path):
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)
    create_res = client.post("/api/v1/sessions", json={"participant_id": "p_finalize", "run_slug": run_slug})
    session_id = create_res.json()["session_id"]
    assert client.post(f"/api/v1/sessions/{session_id}/start").status_code == 200

    early_submit = client.post(f"/api/v1/sessions/{session_id}/final-submit")
    assert early_submit.status_code == 400
    assert "final_submit_ineligible:incomplete_trials" in early_submit.json()["detail"]

    _progress_session_to_awaiting_final_submit(client, session_id)

    finalized = client.post(f"/api/v1/sessions/{session_id}/final-submit")
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "finalized"
    assert finalized.json()["final_submit"] == "accepted"
    assert finalized.json()["already_finalized"] is False

    row = client.app.state.store.fetchone(
        "SELECT status, completed_at FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert row is not None
    assert row["status"] == "finalized"
    assert row["completed_at"] is not None


def test_final_submit_is_idempotent_and_finalized_session_is_locked(tmp_path):
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)
    create_res = client.post("/api/v1/sessions", json={"participant_id": "p_lock", "run_slug": run_slug})
    session_id = create_res.json()["session_id"]
    assert client.post(f"/api/v1/sessions/{session_id}/start").status_code == 200

    _progress_session_to_awaiting_final_submit(client, session_id)
    first_submit = client.post(f"/api/v1/sessions/{session_id}/final-submit")
    assert first_submit.status_code == 200
    second_submit = client.post(f"/api/v1/sessions/{session_id}/final-submit")
    assert second_submit.status_code == 200
    assert second_submit.json()["final_submit"] == "already_finalized"
    assert second_submit.json()["already_finalized"] is True

    next_trial = client.get(f"/api/v1/sessions/{session_id}/next-trial")
    assert next_trial.status_code == 200
    assert next_trial.json()["status"] == "finalized"

    any_trial = client.app.state.store.fetchone(
        "SELECT trial_id FROM session_trials WHERE session_id = ? ORDER BY trial_id LIMIT 1",
        (session_id,),
    )
    assert any_trial is not None
    blocked_submit = client.post(
        f"/api/v1/sessions/{session_id}/trials/{any_trial['trial_id']}/submit",
        json={
            "human_response": "scam",
            "reaction_time_ms": 1000,
            "self_confidence": 70,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
        },
    )
    assert blocked_submit.status_code == 400
    assert "session_finalized" in blocked_submit.json()["detail"]

    blocked_questionnaire = client.post(
        f"/api/v1/sessions/{session_id}/blocks/block_1/questionnaire",
        json={"burden": 10, "trust": 10, "usefulness": 10},
    )
    assert blocked_questionnaire.status_code == 400
    assert "session_finalized" in blocked_questionnaire.json()["detail"]


def test_final_submit_unknown_session_returns_404(tmp_path):
    client = _make_client(tmp_path)
    res = client.post("/api/v1/sessions/sess_missing/final-submit")
    assert res.status_code == 404


def test_live_session_creation_fails_for_non_executable_run_config_without_default_fallback(tmp_path):
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)

    row = client.app.state.store.fetchone(
        "SELECT run_id FROM researcher_runs WHERE public_slug = ?",
        (run_slug,),
    )
    assert row is not None
    client.app.state.store.execute(
        "UPDATE researcher_runs SET config_json = ? WHERE run_id = ?",
        (dumps({"mode": "broken"}), row["run_id"]),
    )

    res = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_non_exec", "run_slug": run_slug},
    )
    assert res.status_code == 400
    assert "missing executable fields" in res.json()["detail"]


def test_session_trial_shape_comes_from_run_config_json(tmp_path):
    db_path = str(tmp_path / "pilot_api.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    client = _make_client(tmp_path)

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
            "run_name": "run cfg shape",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {
                "execution": {
                    "experiment_id": "toy_v1",
                    "task_family": "scam_detection",
                    "n_blocks": 1,
                    "trials_per_block": 2,
                    "practice_trials": 0,
                    "conditions": ["static_help", "monotone_help", "cabdi_lite"],
                    "block_order_strategy": "latin_square",
                    "budget_matching_mode": "matched",
                    "risk_proxy_mode": "pre_render_features_v1",
                    "self_confidence_scale": "0_100_int",
                    "block_questionnaires": ["burden", "trust", "usefulness"],
                }
            },
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    assert researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate").status_code == 200

    create_res = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_run_cfg", "run_slug": run.json()["public_slug"]},
    )
    assert create_res.status_code == 200
    session_id = create_res.json()["session_id"]
    assert client.post(f"/api/v1/sessions/{session_id}/start").status_code == 200
    first = client.get(f"/api/v1/sessions/{session_id}/next-trial")
    assert first.status_code == 200
    assert first.json()["progress"]["total_trials"] == 2

    trial_count = client.app.state.store.fetchone(
        "SELECT COUNT(*) AS n FROM session_trials WHERE session_id = ?",
        (session_id,),
    )
    assert trial_count is not None
    assert trial_count["n"] == 2


def test_session_creation_returns_resume_identity(tmp_path):
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)

    created = client.post("/api/v1/sessions", json={"participant_id": "p_resume_identity", "run_slug": run_slug})
    assert created.status_code == 200
    body = created.json()
    assert body["entry_mode"] == "created"
    assert body["resume_token"]
    assert body["public_session_code"]

    row = client.app.state.store.fetchone(
        "SELECT resume_token_hash, public_session_code FROM participant_sessions WHERE session_id = ?",
        (body["session_id"],),
    )
    assert row is not None
    assert row["resume_token_hash"]
    assert row["public_session_code"] == body["public_session_code"]


def test_resume_info_and_create_session_resume_existing_unfinished_session(tmp_path):
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)

    first = client.post("/api/v1/sessions", json={"participant_id": "p_resume", "run_slug": run_slug}).json()
    session_id = first["session_id"]
    resume_token = first["resume_token"]
    assert client.post(f"/api/v1/sessions/{session_id}/start").status_code == 200

    trial = client.get(f"/api/v1/sessions/{session_id}/next-trial").json()
    submit = client.post(
        f"/api/v1/sessions/{session_id}/trials/{trial['trial_id']}/submit",
        json={
            "human_response": trial["stimulus"]["true_label"],
            "reaction_time_ms": 900,
            "self_confidence": 70,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
        },
    )
    assert submit.status_code == 200

    resume_info = client.post(
        "/api/v1/sessions/resume-info",
        json={"run_slug": run_slug, "resume_token": resume_token},
    )
    assert resume_info.status_code == 200
    assert resume_info.json()["resume_status"] == "resumable"
    assert resume_info.json()["session_id"] == session_id

    resumed = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_resume_other_name", "run_slug": run_slug, "resume_token": resume_token},
    )
    assert resumed.status_code == 200
    assert resumed.json()["entry_mode"] == "resumed"
    assert resumed.json()["session_id"] == session_id

    session_count = client.app.state.store.fetchone(
        "SELECT COUNT(*) AS n FROM participant_sessions WHERE run_id = (SELECT run_id FROM researcher_runs WHERE public_slug = ?)",
        (run_slug,),
    )
    assert session_count is not None
    assert session_count["n"] == 1


def test_resume_invalid_token_is_explicit_and_falls_back_to_new_session(tmp_path):
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)

    invalid_info = client.post(
        "/api/v1/sessions/resume-info",
        json={"run_slug": run_slug, "resume_token": "invalid-token"},
    )
    assert invalid_info.status_code == 200
    assert invalid_info.json()["resume_status"] == "invalid"

    created = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_new_after_invalid", "run_slug": run_slug, "resume_token": "invalid-token"},
    )
    assert created.status_code == 200
    assert created.json()["entry_mode"] == "created"


def test_finalized_session_is_not_resumable_and_does_not_reopen(tmp_path):
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)

    created = client.post("/api/v1/sessions", json={"participant_id": "p_finalized_resume", "run_slug": run_slug}).json()
    session_id = created["session_id"]
    resume_token = created["resume_token"]
    assert client.post(f"/api/v1/sessions/{session_id}/start").status_code == 200
    _progress_session_to_awaiting_final_submit(client, session_id)
    assert client.post(f"/api/v1/sessions/{session_id}/final-submit").status_code == 200

    resume_info = client.post(
        "/api/v1/sessions/resume-info",
        json={"run_slug": run_slug, "resume_token": resume_token},
    )
    assert resume_info.status_code == 200
    assert resume_info.json()["resume_status"] == "finalized"

    resumed = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_finalized_resume_attempt", "run_slug": run_slug, "resume_token": resume_token},
    )
    assert resumed.status_code == 409
    assert resumed.json()["detail"] == "resume_not_allowed:session_finalized"


def test_awaiting_final_submit_session_resumes_without_reopening_trials(tmp_path):
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)

    created = client.post("/api/v1/sessions", json={"participant_id": "p_wait_resume", "run_slug": run_slug}).json()
    session_id = created["session_id"]
    resume_token = created["resume_token"]
    assert client.post(f"/api/v1/sessions/{session_id}/start").status_code == 200
    _progress_session_to_awaiting_final_submit(client, session_id)

    resumed = client.post(
        "/api/v1/sessions",
        json={"participant_id": "p_wait_resume_new", "run_slug": run_slug, "resume_token": resume_token},
    )
    assert resumed.status_code == 200
    assert resumed.json()["entry_mode"] == "resumed"

    start = client.post(f"/api/v1/sessions/{session_id}/start")
    assert start.status_code == 200
    assert start.json()["status"] == "awaiting_final_submit"

    next_trial = client.get(f"/api/v1/sessions/{session_id}/next-trial")
    assert next_trial.status_code == 200
    assert next_trial.json()["status"] == "awaiting_final_submit"
