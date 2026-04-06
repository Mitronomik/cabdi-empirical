from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app
from app.participant_api.persistence.json_codec import loads
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _bootstrap_run(tmp_path) -> str:
    db_path = str(tmp_path / "pilot_help_salience.sqlite3")
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
            "run_name": "help salience run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [upload.json()["stimulus_set_id"]],
        },
    )
    researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate")
    return run.json()["public_slug"]


def test_help_panel_render_metadata_logged_without_risk_recompute(tmp_path):
    client = TestClient(create_app(str(tmp_path / "pilot_help_salience.sqlite3")))
    run_slug = _bootstrap_run(tmp_path)

    create_res = client.post("/api/v1/sessions", json={"run_slug": run_slug})
    session_id = create_res.json()["session_id"]
    client.post(f"/api/v1/sessions/{session_id}/start")

    trial = client.get(f"/api/v1/sessions/{session_id}/next-trial").json()
    risk_bucket_before = trial["policy_decision"]["risk_bucket"]

    event_rows = client.app.state.store.fetchall(
        "SELECT event_type, payload_json FROM trial_event_logs WHERE session_id = ? AND trial_id = ? ORDER BY timestamp",
        (session_id, trial["trial_id"]),
    )
    assistance_events = [row for row in event_rows if row["event_type"] == "assistance_rendered"]
    assert assistance_events
    base_payload = loads(assistance_events[0]["payload_json"])
    assert base_payload["assistance_rendered"] is True
    assert isinstance(base_payload["shown_help_components"], list)
    assert base_payload["panel_visible_on_first_paint"] is None

    submit = client.post(
        f"/api/v1/sessions/{session_id}/trials/{trial['trial_id']}/submit",
        json={
            "human_response": trial["stimulus"]["true_label"],
            "reaction_time_ms": 500,
            "self_confidence": 3,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
            "event_trace": [
                {
                    "event_type": "assistance_rendered",
                    "payload": {
                        "assistance_rendered": True,
                        "panel_visible_on_first_paint": False,
                        "shown_help_components": ["prediction"],
                    },
                }
            ],
        },
    )
    assert submit.status_code == 200

    stored_after = client.app.state.store.fetchone(
        "SELECT risk_bucket FROM session_trials WHERE session_id = ? AND trial_id = ?",
        (session_id, trial["trial_id"]),
    )
    assert stored_after["risk_bucket"] == risk_bucket_before
