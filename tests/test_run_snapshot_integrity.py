from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app
from app.participant_api.persistence.json_codec import dumps, loads
from app.participant_api.services.randomization_service import assign_order_id
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


def _create_active_run_with_execution(
    client: TestClient,
    *,
    stimulus_set_ids: list[str],
    practice_stimulus_set_id: str,
) -> tuple[str, str]:
    run = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "snapshot-protocol-run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"execution": {"n_blocks": 3, "trials_per_block": 2, "practice_trials": 2}},
            "stimulus_set_ids": stimulus_set_ids,
            "practice_stimulus_set_id": practice_stimulus_set_id,
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


def test_snapshot_preserves_protocol_blocks_and_truthful_expected_count(tmp_path) -> None:
    db_path = str(tmp_path / "snapshot-blocks.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)
    main_set_id = _upload_set(researcher, name="main-protocol", n_items=6)
    practice_set_id = _upload_set(researcher, name="practice-protocol", n_items=2)
    _, run_slug = _create_active_run_with_execution(
        researcher,
        stimulus_set_ids=[main_set_id],
        practice_stimulus_set_id=practice_set_id,
    )

    created = participant.post("/api/v1/sessions", json={"run_slug": run_slug})
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    started = participant.post(f"/api/v1/sessions/{session_id}/start")
    assert started.status_code == 200

    session_row = participant.app.state.store.fetchone(
        "SELECT participant_id, expected_trial_count FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    rows = participant.app.state.store.fetchall(
        """
        SELECT block_id, block_index, trial_index, condition, status, is_practice
        FROM session_trials
        WHERE session_id = ?
        ORDER BY block_index, trial_index
        """,
        (session_id,),
    )
    assert len(rows) == int(session_row["expected_trial_count"])
    assert len(rows) == 8

    practice_trials = [row for row in rows if int(row["is_practice"]) == 1]
    main_trials = [row for row in rows if int(row["is_practice"]) == 0]
    assert len(practice_trials) == 2
    main_block_ids = sorted({str(row["block_id"]) for row in main_trials})
    assert main_block_ids == ["block_1", "block_2", "block_3"]

    expected_conditions = ["static_help", "monotone_help", "cabdi_lite"]
    assigned_conditions = assign_order_id(str(session_row["participant_id"]), "toy_v1")[1]
    assert assigned_conditions in [
        expected_conditions,
        ["monotone_help", "cabdi_lite", "static_help"],
        ["cabdi_lite", "static_help", "monotone_help"],
    ]
    for block_index, expected_condition in enumerate(assigned_conditions):
        block_conditions = {row["condition"] for row in main_trials if int(row["block_index"]) == block_index}
        assert block_conditions == {expected_condition}

    participant.app.state.store.execute(
        "UPDATE session_trials SET status = 'completed' WHERE session_id = ? AND block_id = 'block_1'",
        (session_id,),
    )
    blocked_block = participant.app.state.trial_service._questionnaire_block_gate(session_id)
    assert blocked_block == "block_1"


def test_snapshot_materializes_practice_bank_and_persists_true_per_trial_provenance(tmp_path) -> None:
    db_path = str(tmp_path / "snapshot-provenance.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)
    main_set_id = _upload_set(researcher, name="main-bank", n_items=6)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    _, run_slug = _create_active_run_with_execution(
        researcher,
        stimulus_set_ids=[main_set_id],
        practice_stimulus_set_id=practice_set_id,
    )

    created = participant.post("/api/v1/sessions", json={"run_slug": run_slug})
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    started = participant.post(f"/api/v1/sessions/{session_id}/start")
    assert started.status_code == 200

    rows = participant.app.state.store.fetchall(
        """
        SELECT trial_id, block_id, is_practice, source_stimulus_set_ids_json
        FROM session_trials
        WHERE session_id = ?
        ORDER BY block_index, trial_index
        """,
        (session_id,),
    )
    assert rows
    for row in rows:
        source_ids = loads(row["source_stimulus_set_ids_json"])
        if int(row["is_practice"]) == 1:
            assert row["block_id"] == "practice"
            assert source_ids == [practice_set_id]
        else:
            assert row["block_id"] != "practice"
            assert source_ids == [main_set_id]


def test_snapshot_integrity_fails_when_trial_provenance_is_mutated_to_non_run_source(tmp_path) -> None:
    db_path = str(tmp_path / "snapshot-provenance-integrity.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)
    main_set_id = _upload_set(researcher, name="main-bank", n_items=6)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    outside_set_id = _upload_set(researcher, name="outside-bank", n_items=1)
    _, run_slug = _create_active_run_with_execution(
        researcher,
        stimulus_set_ids=[main_set_id],
        practice_stimulus_set_id=practice_set_id,
    )

    created = participant.post("/api/v1/sessions", json={"run_slug": run_slug})
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    started = participant.post(f"/api/v1/sessions/{session_id}/start")
    assert started.status_code == 200

    mutated_trial = participant.app.state.store.fetchone(
        "SELECT trial_id FROM session_trials WHERE session_id = ? AND is_practice = 0 ORDER BY trial_id LIMIT 1",
        (session_id,),
    )
    assert mutated_trial is not None
    participant.app.state.store.execute(
        "UPDATE session_trials SET source_stimulus_set_ids_json = ? WHERE trial_id = ?",
        (dumps([outside_set_id]), mutated_trial["trial_id"]),
    )
    next_trial = participant.get(f"/api/v1/sessions/{session_id}/next-trial")
    assert next_trial.status_code == 400
    assert "outside run stimulus-set definition" in next_trial.json()["detail"]
