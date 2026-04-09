from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app
from app.participant_api.persistence.json_codec import dumps, loads
from app.researcher_api.main import create_app as create_researcher_app


def _login(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _upload_set(client: TestClient, *, name: str, n_items: int) -> str:
    rows = []
    for idx in range(n_items):
        rows.append(
            (
                '{"stimulus_id":"%s","task_family":"scam_detection","content_type":"text",'
                '"payload":{"title":"Case","body":"%s"},"true_label":"scam","difficulty_prior":"low",'
                '"model_prediction":"scam","model_confidence":"high","model_correct":true,"eligible_sets":["demo"]}'
            )
            % (f"{name}_{idx+1}", idx + 1)
        )
    res = client.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", "\n".join(rows) + "\n", "application/json")},
        data={"name": name, "source_format": "jsonl"},
    )
    assert res.status_code == 200
    return str(res.json()["stimulus_set_id"])


def _create_and_activate_run(
    client: TestClient,
    *,
    main_set_ids: list[str],
    practice_set_id: str | None = None,
    n_blocks: int = 3,
    practice_trials: int = 2,
) -> tuple[str, str]:
    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "invariant-run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"execution": {"n_blocks": n_blocks, "trials_per_block": 2, "practice_trials": practice_trials}},
            "stimulus_set_ids": main_set_ids,
            "practice_stimulus_set_id": practice_set_id,
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    run_id = str(create.json()["run_id"])
    assert client.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200
    return run_id, str(create.json()["public_slug"])


def _start_session(participant: TestClient, *, run_slug: str) -> str:
    created = participant.post("/api/v1/sessions", json={"run_slug": run_slug})
    assert created.status_code == 200
    session_id = str(created.json()["session_id"])
    started = participant.post(f"/api/v1/sessions/{session_id}/start")
    assert started.status_code == 200
    return session_id


def test_start_session_sets_trial_stage_when_no_practice_trials_materialize(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-start-stage-trial.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=4)
    _, run_slug = _create_and_activate_run(researcher, main_set_ids=[main_set_id], practice_set_id=None, practice_trials=0)
    session_id = _start_session(participant, run_slug=run_slug)

    session_row = participant.app.state.store.fetchone(
        "SELECT current_stage FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert session_row is not None
    assert str(session_row["current_stage"]) == "trial"


def test_start_session_sets_practice_stage_when_practice_trials_materialize(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-start-stage-practice.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=4)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    _, run_slug = _create_and_activate_run(
        researcher,
        main_set_ids=[main_set_id],
        practice_set_id=practice_set_id,
        practice_trials=2,
    )
    session_id = _start_session(participant, run_slug=run_slug)

    session_row = participant.app.state.store.fetchone(
        "SELECT current_stage FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert session_row is not None
    assert str(session_row["current_stage"]) == "practice"


def test_update_progress_sets_trial_stage_when_snapshot_has_no_practice_trials(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-update-progress-no-practice.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=4)
    _, run_slug = _create_and_activate_run(researcher, main_set_ids=[main_set_id], practice_set_id=None, practice_trials=0)
    session_id = _start_session(participant, run_slug=run_slug)

    participant.app.state.store.execute(
        "UPDATE session_trials SET status = 'served', completed_at = NULL WHERE session_id = ?",
        (session_id,),
    )
    participant.app.state.session_service.update_progress(session_id)

    session_row = participant.app.state.store.fetchone(
        "SELECT current_stage, current_block_index, current_trial_index FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert session_row is not None
    assert str(session_row["current_stage"]) == "trial"
    assert int(session_row["current_block_index"]) == -1
    assert int(session_row["current_trial_index"]) == 0


def test_update_progress_sets_practice_stage_when_snapshot_has_practice_trials(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-update-progress-with-practice.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=4)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    _, run_slug = _create_and_activate_run(
        researcher,
        main_set_ids=[main_set_id],
        practice_set_id=practice_set_id,
        practice_trials=2,
    )
    session_id = _start_session(participant, run_slug=run_slug)

    participant.app.state.store.execute(
        "UPDATE session_trials SET status = 'served', completed_at = NULL WHERE session_id = ?",
        (session_id,),
    )
    participant.app.state.session_service.update_progress(session_id)

    session_row = participant.app.state.store.fetchone(
        "SELECT current_stage, current_block_index, current_trial_index FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert session_row is not None
    assert str(session_row["current_stage"]) == "practice"
    assert int(session_row["current_block_index"]) == -1
    assert int(session_row["current_trial_index"]) == 0


def test_update_progress_with_completed_practice_trial_keeps_trial_transition_semantics(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-update-progress-completed-practice.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=4)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    _, run_slug = _create_and_activate_run(
        researcher,
        main_set_ids=[main_set_id],
        practice_set_id=practice_set_id,
        practice_trials=2,
    )
    session_id = _start_session(participant, run_slug=run_slug)

    participant.app.state.store.execute(
        """
        UPDATE session_trials
        SET status = 'completed', completed_at = '2026-01-01T00:00:00+00:00'
        WHERE session_id = ? AND is_practice = 1
          AND trial_id = (
            SELECT trial_id
            FROM session_trials
            WHERE session_id = ? AND is_practice = 1
            ORDER BY trial_index
            LIMIT 1
          )
        """,
        (session_id, session_id),
    )
    participant.app.state.session_service.update_progress(session_id)

    session_row = participant.app.state.store.fetchone(
        "SELECT current_stage, current_block_index, current_trial_index FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert session_row is not None
    assert str(session_row["current_stage"]) == "practice"
    assert int(session_row["current_block_index"]) == -1
    assert int(session_row["current_trial_index"]) == 1


def test_start_session_restart_preserves_truthful_stage_and_indices_with_practice_snapshot(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-restart-preserve-practice.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=4)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    _, run_slug = _create_and_activate_run(
        researcher,
        main_set_ids=[main_set_id],
        practice_set_id=practice_set_id,
        practice_trials=2,
    )
    session_id = _start_session(participant, run_slug=run_slug)

    participant.app.state.store.execute(
        """
        UPDATE participant_sessions
        SET current_stage = 'questionnaire', current_block_index = 0, current_trial_index = 1
        WHERE session_id = ?
        """,
        (session_id,),
    )

    restarted = participant.post(f"/api/v1/sessions/{session_id}/start")
    assert restarted.status_code == 200
    assert restarted.json()["status"] == "in_progress"

    session_row = participant.app.state.store.fetchone(
        "SELECT current_stage, current_block_index, current_trial_index FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert session_row is not None
    assert str(session_row["current_stage"]) == "questionnaire"
    assert int(session_row["current_block_index"]) == 0
    assert int(session_row["current_trial_index"]) == 1


def test_start_session_restart_preserves_truthful_stage_and_indices_without_practice_snapshot(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-restart-preserve-trial.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=4)
    _, run_slug = _create_and_activate_run(researcher, main_set_ids=[main_set_id], practice_set_id=None, practice_trials=0)
    session_id = _start_session(participant, run_slug=run_slug)

    participant.app.state.store.execute(
        """
        UPDATE participant_sessions
        SET current_stage = 'trial', current_block_index = 1, current_trial_index = 2
        WHERE session_id = ?
        """,
        (session_id,),
    )

    restarted = participant.post(f"/api/v1/sessions/{session_id}/start")
    assert restarted.status_code == 200
    assert restarted.json()["status"] == "in_progress"

    session_row = participant.app.state.store.fetchone(
        "SELECT current_stage, current_block_index, current_trial_index FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert session_row is not None
    assert str(session_row["current_stage"]) == "trial"
    assert int(session_row["current_block_index"]) == 1
    assert int(session_row["current_trial_index"]) == 2


def test_start_session_unpauses_without_clobbering_truthful_progress_state(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-start-paused-preserve.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=4)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    _, run_slug = _create_and_activate_run(
        researcher,
        main_set_ids=[main_set_id],
        practice_set_id=practice_set_id,
        practice_trials=2,
    )
    session_id = _start_session(participant, run_slug=run_slug)

    participant.app.state.store.execute(
        """
        UPDATE participant_sessions
        SET status = 'paused', current_stage = 'questionnaire', current_block_index = 2, current_trial_index = 0
        WHERE session_id = ?
        """,
        (session_id,),
    )

    resumed_start = participant.post(f"/api/v1/sessions/{session_id}/start")
    assert resumed_start.status_code == 200
    assert resumed_start.json()["status"] == "in_progress"

    session_row = participant.app.state.store.fetchone(
        "SELECT status, current_stage, current_block_index, current_trial_index FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert session_row is not None
    assert str(session_row["status"]) == "in_progress"
    assert str(session_row["current_stage"]) == "questionnaire"
    assert int(session_row["current_block_index"]) == 2
    assert int(session_row["current_trial_index"]) == 0


def test_invariant_protocol_blocks_preserved_in_session_snapshot(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-invariants.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=6)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    _, run_slug = _create_and_activate_run(researcher, main_set_ids=[main_set_id], practice_set_id=practice_set_id)
    session_id = _start_session(participant, run_slug=run_slug)

    rows = participant.app.state.store.fetchall(
        """
        SELECT block_id, block_index, trial_index, is_practice
        FROM session_trials
        WHERE session_id = ?
        ORDER BY block_index, trial_index
        """,
        (session_id,),
    )

    assert len(rows) == 8
    assert sum(int(row["is_practice"]) for row in rows) == 2

    practice_rows = [row for row in rows if int(row["is_practice"]) == 1]
    assert {str(row["block_id"]) for row in practice_rows} == {"practice"}
    assert all(int(row["block_index"]) == -1 for row in practice_rows)

    main_rows = [row for row in rows if int(row["is_practice"]) == 0]
    assert {str(row["block_id"]) for row in main_rows} == {"block_1", "block_2", "block_3"}
    per_block_counts: dict[int, int] = {}
    for row in main_rows:
        block_index = int(row["block_index"])
        per_block_counts[block_index] = per_block_counts.get(block_index, 0) + 1
    assert per_block_counts == {0: 2, 1: 2, 2: 2}


def test_invariant_practice_and_main_trial_provenance_remain_truthful(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-provenance.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=6)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    _, run_slug = _create_and_activate_run(researcher, main_set_ids=[main_set_id], practice_set_id=practice_set_id)
    session_id = _start_session(participant, run_slug=run_slug)

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


def test_invariant_snapshot_integrity_rejects_fake_trial_provenance(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-fake-provenance.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=4)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    _, run_slug = _create_and_activate_run(researcher, main_set_ids=[main_set_id], practice_set_id=practice_set_id)
    session_id = _start_session(participant, run_slug=run_slug)

    victim = participant.app.state.store.fetchone(
        "SELECT trial_id FROM session_trials WHERE session_id = ? ORDER BY trial_id LIMIT 1",
        (session_id,),
    )
    assert victim is not None
    participant.app.state.store.execute(
        "UPDATE session_trials SET source_stimulus_set_ids_json = ? WHERE trial_id = ?",
        (dumps([]), victim["trial_id"]),
    )

    next_trial = participant.get(f"/api/v1/sessions/{session_id}/next-trial")
    assert next_trial.status_code == 400
    assert "provenance is missing source stimulus-set ids" in str(next_trial.json()["detail"])


def test_invariant_researcher_summary_runtime_and_snapshot_totals_agree(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-totals.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    main_set_id = _upload_set(researcher, name="main-bank", n_items=6)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    run_id, run_slug = _create_and_activate_run(researcher, main_set_ids=[main_set_id], practice_set_id=practice_set_id)

    run_details = researcher.get(f"/admin/api/v1/runs/{run_id}")
    assert run_details.status_code == 200
    expected = int(run_details.json()["run_summary"]["expected_trial_count"])
    assert expected == 8

    session_id = _start_session(participant, run_slug=run_slug)
    session_row = participant.app.state.store.fetchone(
        "SELECT expected_trial_count FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert session_row is not None
    persisted_expected = int(session_row["expected_trial_count"])

    first_trial = participant.get(f"/api/v1/sessions/{session_id}/next-trial")
    assert first_trial.status_code == 200
    runtime_total = int(first_trial.json()["progress"]["total_trials"])

    snapshot_count_row = participant.app.state.store.fetchone(
        "SELECT COUNT(*) AS n FROM session_trials WHERE session_id = ?",
        (session_id,),
    )
    assert snapshot_count_row is not None
    snapshot_count = int(snapshot_count_row["n"])

    assert expected == persisted_expected == runtime_total == snapshot_count


def test_invariant_single_selected_main_bank_does_not_merge_unselected_banks(tmp_path) -> None:
    db_path = str(tmp_path / "run-session-single-bank.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    participant = TestClient(create_app(db_path))
    _login(researcher)

    selected_main_set_id = _upload_set(researcher, name="selected-main", n_items=3)
    _ = _upload_set(researcher, name="unselected-main", n_items=9)
    practice_set_id = _upload_set(researcher, name="practice-bank", n_items=2)
    run_id, run_slug = _create_and_activate_run(researcher, main_set_ids=[selected_main_set_id], practice_set_id=practice_set_id)

    run_details = researcher.get(f"/admin/api/v1/runs/{run_id}")
    assert run_details.status_code == 200
    summary = run_details.json()["run_summary"]
    assert summary["selected_main_stimulus_set_ids"] == [selected_main_set_id]
    assert [bank["stimulus_set_id"] for bank in summary["banks"]] == [selected_main_set_id]
    assert summary["main_item_count"] == 3

    session_id = _start_session(participant, run_slug=run_slug)
    session_row = participant.app.state.store.fetchone(
        "SELECT source_stimulus_set_ids_json FROM participant_sessions WHERE session_id = ?",
        (session_id,),
    )
    assert session_row is not None
    assert loads(session_row["source_stimulus_set_ids_json"]) == [selected_main_set_id, practice_set_id]

    main_trial_rows = participant.app.state.store.fetchall(
        "SELECT source_stimulus_set_ids_json FROM session_trials WHERE session_id = ? AND is_practice = 0",
        (session_id,),
    )
    assert main_trial_rows
    for row in main_trial_rows:
        assert loads(row["source_stimulus_set_ids_json"]) == [selected_main_set_id]
