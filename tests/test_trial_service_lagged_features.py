from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app
from app.participant_api.persistence.json_codec import loads
from app.participant_api.services.trial_service import _latency_bucket_from_summaries
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _bootstrap_small_run(tmp_path) -> str:
    db_path = str(tmp_path / "pilot_lagged.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    payload = (
        '{"stimulus_id":"s1","task_family":"scam_detection","content_type":"text","payload":{"title":"Case","body":"a"},'
        '"true_label":"not_scam","difficulty_prior":"low","model_prediction":"scam","model_confidence":"high",'
        '"model_correct":false,"eligible_sets":["demo"]}\n'
        '{"stimulus_id":"s2","task_family":"scam_detection","content_type":"text","payload":{"title":"Case 2","body":"b"},'
        '"true_label":"not_scam","difficulty_prior":"low","model_prediction":"scam","model_confidence":"high",'
        '"model_correct":false,"eligible_sets":["demo"]}\n'
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
            "run_name": "lagged features run",
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
                    "self_confidence_scale": "4_point",
                    "block_questionnaires": ["burden", "trust", "usefulness"],
                }
            },
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    activate = researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate")
    assert activate.status_code == 200
    return run.json()["public_slug"]


def test_live_routing_uses_prior_persisted_summaries_only(tmp_path):
    db_path = str(tmp_path / "pilot_lagged.sqlite3")
    client = TestClient(create_app(db_path))
    run_slug = _bootstrap_small_run(tmp_path)

    created = client.post("/api/v1/sessions", json={"run_slug": run_slug})
    session_id = created.json()["session_id"]
    client.post(f"/api/v1/sessions/{session_id}/start")

    first_trial = client.get(f"/api/v1/sessions/{session_id}/next-trial").json()
    assert first_trial["policy_decision"]["risk_bucket"] == "low"

    first_row = client.app.state.store.fetchone(
        "SELECT pre_render_features_json FROM session_trials WHERE trial_id = ?",
        (first_trial["trial_id"],),
    )
    first_features = loads(first_row["pre_render_features_json"])
    assert first_features["recent_error_count_last_3"] == 0
    assert first_features["recent_blind_accept_count_last_3"] == 0
    assert first_features["recent_latency_z_bucket"] == "medium"
    assert first_features["prior_completed_trials_considered"] == 0

    submit = client.post(
        f"/api/v1/sessions/{session_id}/trials/{first_trial['trial_id']}/submit",
        json={
            "human_response": first_trial["stimulus"]["model_prediction"],
            "reaction_time_ms": 2000,
            "self_confidence": 1,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
        },
    )
    assert submit.status_code == 200

    second_trial = client.get(f"/api/v1/sessions/{session_id}/next-trial").json()
    assert second_trial["policy_decision"]["risk_bucket"] == "extreme"

    second_row = client.app.state.store.fetchone(
        "SELECT pre_render_features_json FROM session_trials WHERE trial_id = ?",
        (second_trial["trial_id"],),
    )
    second_features = loads(second_row["pre_render_features_json"])
    assert second_features["recent_error_count_last_3"] == 1
    assert second_features["recent_blind_accept_count_last_3"] == 1
    assert second_features["recent_latency_z_bucket"] == "high"
    assert second_features["prior_completed_trials_considered"] == 1


def test_latency_bucket_fallback_is_deterministic_for_missing_or_sparse_inputs():
    assert _latency_bucket_from_summaries([]) == "medium"
    assert _latency_bucket_from_summaries([{"reaction_time_ms": None}]) == "medium"
    assert _latency_bucket_from_summaries([{"reaction_time_ms": "bad"}, {"reaction_time_ms": 1000}]) == "medium"
    assert _latency_bucket_from_summaries([{"reaction_time_ms": 700}]) == "low"
    assert _latency_bucket_from_summaries([{"reaction_time_ms": 2000}]) == "high"


def test_event_trace_complements_summary_for_blind_accept_and_error_flags(tmp_path):
    db_path = str(tmp_path / "pilot_lagged.sqlite3")
    client = TestClient(create_app(db_path))
    run_slug = _bootstrap_small_run(tmp_path)

    created = client.post("/api/v1/sessions", json={"run_slug": run_slug})
    session_id = created.json()["session_id"]
    client.post(f"/api/v1/sessions/{session_id}/start")

    first_trial = client.get(f"/api/v1/sessions/{session_id}/next-trial").json()
    submit = client.post(
        f"/api/v1/sessions/{session_id}/trials/{first_trial['trial_id']}/submit",
        json={
            "human_response": first_trial["stimulus"]["model_prediction"],
            "reaction_time_ms": 600,
            "self_confidence": 3,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
            "event_trace": [
                {"event_type": "trial_completed", "payload": {"reaction_time_ms": 2300}},
                {"event_type": "verification_checked", "payload": {"value": True}},
            ],
        },
    )
    assert submit.status_code == 200

    # Corrupt summary row to force event-informed fallback path.
    client.app.state.store.execute(
        "UPDATE trial_summary_logs SET summary_json = ? WHERE session_id = ? AND trial_id = ?",
        ("{}", session_id, first_trial["trial_id"]),
    )

    second_trial = client.get(f"/api/v1/sessions/{session_id}/next-trial").json()
    second_row = client.app.state.store.fetchone(
        "SELECT pre_render_features_json FROM session_trials WHERE trial_id = ?",
        (second_trial["trial_id"],),
    )
    second_features = loads(second_row["pre_render_features_json"])
    assert second_features["recent_error_count_last_3"] == 1
    assert second_features["recent_blind_accept_count_last_3"] == 0
    assert second_features["recent_latency_z_bucket"] == "low"
