from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.participant_api.persistence.json_codec import dumps
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
    assert res.json()["ok"] is True
    assert res.json()["validation_status"] == "valid"
    return res.json()["stimulus_set_id"]


def _complete_one_non_practice_trial(participant: TestClient, session_id: str) -> str:
    assert participant.post(f"/api/v1/sessions/{session_id}/start").status_code == 200
    for _ in range(12):
        trial_res = participant.get(f"/api/v1/sessions/{session_id}/next-trial")
        assert trial_res.status_code == 200
        trial = trial_res.json()
        if trial.get("no_more_trials"):
            break
        assert participant.post(
            f"/api/v1/sessions/{session_id}/trials/{trial['trial_id']}/submit",
            json={
                "human_response": trial["stimulus"]["model_prediction"],
                "reaction_time_ms": 1200,
                "self_confidence": 3,
                "reason_clicked": False,
                "evidence_opened": False,
                "verification_completed": False,
            },
        ).status_code == 200
        if trial["block_id"] != "practice":
            return str(trial["trial_id"])
    raise AssertionError("Failed to complete a non-practice trial")


def test_create_run_and_session_monitor_and_diagnostics(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    participant = TestClient(create_participant_app(db_path))

    stimulus_set_id = _upload_stimulus(researcher)

    create_run = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "run alpha",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 1},
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
        json={"run_slug": create_run.json()["public_slug"], "language": "ru"},
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
    _login_researcher(researcher)

    stimulus_set_id = _upload_stimulus(researcher)
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "lifecycle run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 1},
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

    close = researcher.post(f"/admin/api/v1/runs/{run_id}/close", json={"confirm_run_id": run_id})
    assert close.status_code == 200
    assert close.json()["status"] == "closed"

    activate_closed = researcher.post(f"/admin/api/v1/runs/{run_id}/activate")
    assert activate_closed.status_code == 400
    assert "Invalid run status transition" in activate_closed.json()["detail"]


def test_closed_runs_remain_readable_for_diagnostics_and_exports(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    participant = TestClient(create_participant_app(db_path))

    stimulus_set_id = _upload_stimulus(researcher)
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "close-compatible run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 1},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    run_id = run_res.json()["run_id"]
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200
    assert participant.post(
        "/api/v1/sessions",
        json={"run_slug": run_res.json()["public_slug"]},
    ).status_code == 200
    closed = researcher.post(f"/admin/api/v1/runs/{run_id}/close", json={"confirm_run_id": run_id})
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    sessions = researcher.get(f"/admin/api/v1/runs/{run_id}/sessions")
    assert sessions.status_code == 200
    assert sessions.json()["run_status"] == "closed"
    diagnostics = researcher.get(f"/admin/api/v1/runs/{run_id}/diagnostics")
    assert diagnostics.status_code == 200
    exports = researcher.get(f"/admin/api/v1/runs/{run_id}/exports")
    assert exports.status_code == 200


def test_close_run_requires_explicit_confirmation_payload(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)

    stimulus_set_id = _upload_stimulus(researcher)
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "close confirm run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 1},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    run_id = run_res.json()["run_id"]
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200

    missing = researcher.post(f"/admin/api/v1/runs/{run_id}/close")
    assert missing.status_code == 422

    mismatch = researcher.post(f"/admin/api/v1/runs/{run_id}/close", json={"confirm_run_id": "wrong"})
    assert mismatch.status_code == 400

    ok = researcher.post(f"/admin/api/v1/runs/{run_id}/close", json={"confirm_run_id": run_id})
    assert ok.status_code == 200


def test_session_monitor_distinguishes_awaiting_final_submit_and_finalized(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    participant = TestClient(create_participant_app(db_path))

    stimulus_set_id = _upload_stimulus(researcher)
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "status split run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 1},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    run_id = run_res.json()["run_id"]
    run_slug = run_res.json()["public_slug"]
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200

    awaiting_session = participant.post(
        "/api/v1/sessions",
        json={"run_slug": run_slug},
    ).json()["session_id"]
    finalized_session = participant.post(
        "/api/v1/sessions",
        json={"run_slug": run_slug},
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


def test_run_diagnostics_and_exports_share_run_scoped_truth(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    participant = TestClient(create_participant_app(db_path))

    stimulus_set_id = _upload_stimulus(researcher)
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "diag-export coherence",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 1},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    run_id = run_res.json()["run_id"]
    run_slug = run_res.json()["public_slug"]
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200

    s1 = participant.post("/api/v1/sessions", json={"run_slug": run_slug}).json()["session_id"]
    s2 = participant.post("/api/v1/sessions", json={"run_slug": run_slug}).json()["session_id"]
    participant.app.state.store.execute(
        "UPDATE participant_sessions SET status = 'awaiting_final_submit' WHERE session_id = ?",
        (s1,),
    )
    participant.app.state.store.execute(
        "UPDATE participant_sessions SET status = 'finalized', completed_at = '2026-01-01T00:00:00+00:00' WHERE session_id = ?",
        (s2,),
    )

    diagnostics = researcher.get(f"/admin/api/v1/runs/{run_id}/diagnostics")
    exports = researcher.get(f"/admin/api/v1/runs/{run_id}/exports")
    assert diagnostics.status_code == 200
    assert exports.status_code == 200
    d_body = diagnostics.json()
    e_body = exports.json()
    assert d_body["session_counts"]["awaiting_final_submit"] == 1
    assert d_body["session_counts"]["finalized"] == 1
    assert len(e_body["session_summary_json"]) == 2


def test_budget_diagnostics_detect_display_and_interaction_drift(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    participant = TestClient(create_participant_app(db_path))
    stimulus_set_id = _upload_stimulus(researcher)
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "budget-drift run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 1},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    run_id = run_res.json()["run_id"]
    run_slug = run_res.json()["public_slug"]
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200

    session_id = participant.post(
        "/api/v1/sessions",
        json={"run_slug": run_slug},
    ).json()["session_id"]
    trial_id = _complete_one_non_practice_trial(participant, session_id)
    participant.app.state.store.execute(
        "UPDATE session_trials SET policy_decision_json = ?, risk_bucket = ? WHERE trial_id = ?",
        (
            dumps(
                {
                    "condition": "static_help",
                    "risk_bucket": "low",
                    "show_prediction": True,
                    "show_confidence": True,
                    "show_rationale": "inline",
                    "show_evidence": True,
                    "verification_mode": "forced_checkbox",
                    "compression_mode": "none",
                    "max_extra_steps": 2,
                    "ui_help_level": "fixed",
                    "ui_verification_level": "fixed",
                    "budget_signature": {
                        "shown_components_count": 4,
                        "text_tokens_shown": 80,
                        "evidence_available_count": 1,
                        "max_extra_steps": 2,
                    },
                }
            ),
            "low",
            trial_id,
        ),
    )
    participant.app.state.store.execute(
        "UPDATE trial_summary_logs SET summary_json = ? WHERE session_id = ? AND trial_id = ?",
        (
            dumps(
                {
                    "participant_id": "opaque_budget_subject",
                    "session_id": session_id,
                    "experiment_id": "toy_v1",
                    "condition": "static_help",
                    "stimulus_id": "s1",
                    "task_family": "scam_detection",
                    "true_label": "scam",
                    "human_response": "scam",
                    "correct_or_not": True,
                    "model_prediction": "scam",
                    "model_confidence": "high",
                    "model_correct_or_not": True,
                    "risk_bucket": "low",
                    "shown_help_level": "fixed",
                    "shown_verification_level": "fixed",
                    "shown_components": ["prediction", "confidence", "rationale", "evidence"],
                    "accepted_model_advice": True,
                    "overrode_model": False,
                    "verification_required": True,
                    "verification_completed": True,
                    "reason_clicked": True,
                    "evidence_opened": True,
                    "reaction_time_ms": 1200,
                    "self_confidence": 3,
                }
            ),
            session_id,
            trial_id,
        ),
    )

    diagnostics = researcher.get(f"/admin/api/v1/runs/{run_id}/diagnostics")
    assert diagnostics.status_code == 200
    body = diagnostics.json()
    kinds = {flag["kind"] for flag in body["budget_tolerance_flags"]}
    assert "text_tolerance_exceeded" in kinds
    assert "display_tolerance_exceeded" in kinds
    assert "interaction_tolerance_exceeded" in kinds
    assert "hard_cap_exceeded" in kinds
    assert "budget_observed_by_condition" in body
    assert "budget_reference_by_condition" in body


def test_budget_diagnostics_warn_on_incomplete_basis(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    participant = TestClient(create_participant_app(db_path))
    stimulus_set_id = _upload_stimulus(researcher)
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "budget-incomplete run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 1},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    run_id = run_res.json()["run_id"]
    run_slug = run_res.json()["public_slug"]
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200
    session_id = participant.post(
        "/api/v1/sessions",
        json={"run_slug": run_slug},
    ).json()["session_id"]
    _complete_one_non_practice_trial(participant, session_id)
    participant.app.state.store.execute(
        "UPDATE session_trials SET policy_decision_json = NULL WHERE session_id = ? AND block_id != 'practice' AND status = 'completed'",
        (session_id,),
    )

    diagnostics = researcher.get(f"/admin/api/v1/runs/{run_id}/diagnostics")
    assert diagnostics.status_code == 200
    body = diagnostics.json()
    assert any(flag["kind"] == "insufficient_budget_data" for flag in body["budget_tolerance_flags"])
    assert any("Budget diagnostics are incomplete" in warning for warning in body["warnings"])
