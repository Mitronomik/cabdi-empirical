from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app
from app.participant_api.persistence.json_codec import dumps, loads
from app.researcher_api.main import create_app as create_researcher_app


def _login(client: TestClient) -> None:
    assert client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"}).status_code == 200


def _upload_set(client: TestClient, *, name: str, n_items: int = 2) -> str:
    rows = []
    for idx in range(n_items):
        rows.append(
            (
                '{"stimulus_id":"%s","task_family":"scam_detection","content_type":"text",'
                '"payload":{"title":"Case","body":"item-%s"},"true_label":"scam","difficulty_prior":"low",'
                '"model_prediction":"scam","model_confidence":"high","model_correct":true,"eligible_sets":["demo"]}'
            )
            % (f"{name}_{idx+1}", idx + 1)
        )
    payload = "\n".join(rows) + "\n"
    res = client.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", payload, "application/json")},
        data={"name": name, "source_format": "jsonl"},
    )
    assert res.status_code == 200
    return str(res.json()["stimulus_set_id"])


def _create_active_run(client: TestClient, *, stimulus_set_ids: list[str]) -> tuple[str, str]:
    run = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "snapshot-run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": stimulus_set_ids,
            "aggregation_mode": "single",
        },
    )
    assert run.status_code == 200
    run_id = run.json()["run_id"]
    assert client.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200
    return run_id, run.json()["public_slug"]


def test_session_cannot_start_without_run_id(tmp_path) -> None:
    db_path = str(tmp_path / "snapshot.sqlite3")
    participant = TestClient(create_app(db_path))
    participant.app.state.store.execute(
        """
        INSERT INTO participant_sessions(
            session_id, participant_id, experiment_id, run_id, assigned_order, stimulus_set_map,
            current_block_index, current_trial_index, status, created_at, started_at, completed_at,
            last_activity_at, device_info, language, expected_trial_count, source_stimulus_set_ids_json, snapshot_frozen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), NULL, NULL, datetime('now'), ?, ?, ?, ?, ?)
        """,
        ("sess_bad", "anon_bad", "toy_v1", "", "order_1", "{}", -1, 0, "created", "{}", "en", 1, "[]", None),
    )
    start = participant.post("/api/v1/sessions/sess_bad/start")
    assert start.status_code == 400
    assert "without run_id" in start.json()["detail"]


def test_session_trial_snapshot_freezes_on_start_and_stays_stable(tmp_path) -> None:
    db_path = str(tmp_path / "snapshot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)
    stimulus_set_id = _upload_set(researcher, name="main-bank", n_items=3)
    _, run_slug = _create_active_run(researcher, stimulus_set_ids=[stimulus_set_id])

    created = participant.post("/api/v1/sessions", json={"run_slug": run_slug})
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    before = participant.app.state.store.fetchone("SELECT COUNT(*) AS n FROM session_trials WHERE session_id = ?", (session_id,))
    assert int(before["n"]) == 0

    started = participant.post(f"/api/v1/sessions/{session_id}/start")
    assert started.status_code == 200
    session_row = participant.app.state.store.fetchone(
        "SELECT expected_trial_count, source_stimulus_set_ids_json, snapshot_frozen_at FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert int(session_row["expected_trial_count"]) == 3
    assert loads(session_row["source_stimulus_set_ids_json"]) == [stimulus_set_id]
    assert session_row["snapshot_frozen_at"] is not None

    counts = participant.app.state.store.fetchone(
        """
        SELECT COUNT(*) AS n, MIN(expected_trial_count) AS min_expected, MAX(expected_trial_count) AS max_expected,
               MIN(is_practice) AS min_practice, MAX(payload_schema_version) AS schema_version
        FROM session_trials WHERE session_id = ?
        """,
        (session_id,),
    )
    assert int(counts["n"]) == int(session_row["expected_trial_count"])
    assert int(counts["min_expected"]) == int(session_row["expected_trial_count"])
    assert str(counts["schema_version"]).startswith("stimulus_payload.")

    first_before = participant.app.state.store.fetchone(
        "SELECT stimulus_json FROM session_trials WHERE session_id = ? ORDER BY trial_id LIMIT 1",
        (session_id,),
    )
    researcher.app.state.store.execute(
        "UPDATE researcher_stimulus_sets SET items_json = ? WHERE stimulus_set_id = ?",
        (dumps([]), stimulus_set_id),
    )
    first_after = participant.app.state.store.fetchone(
        "SELECT stimulus_json FROM session_trials WHERE session_id = ? ORDER BY trial_id LIMIT 1",
        (session_id,),
    )
    assert first_after["stimulus_json"] == first_before["stimulus_json"]
