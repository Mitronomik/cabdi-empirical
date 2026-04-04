from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.participant_api.persistence.backup_restore import backup_database, restore_database
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _seed_minimal_run(tmp_db: str) -> tuple[str, str]:
    researcher = TestClient(create_researcher_app(tmp_db))
    participant = TestClient(create_participant_app(tmp_db))
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
    assert upload.status_code == 200

    run = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "backup run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "backup-test"},
            "stimulus_set_ids": [upload.json()["stimulus_set_id"]],
        },
    )
    assert run.status_code == 200
    run_id = run.json()["run_id"]
    run_slug = run.json()["public_slug"]
    assert researcher.post(f"/admin/api/v1/runs/{run_id}/activate").status_code == 200

    session = participant.post("/api/v1/sessions", json={"participant_id": "p_backup", "run_slug": run_slug})
    assert session.status_code == 200
    session_id = session.json()["session_id"]
    assert participant.post(f"/api/v1/sessions/{session_id}/start").status_code == 200

    next_trial = participant.get(f"/api/v1/sessions/{session_id}/next-trial")
    trial = next_trial.json()
    submit = participant.post(
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
    return run_id, session_id


def test_backup_restore_round_trip_and_restart_survivability(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    run_id, session_id = _seed_minimal_run(db_path)

    backup_path = tmp_path / "backup.json"
    backup_result = backup_database(db_target=db_path, output_path=str(backup_path))
    assert backup_result["schema_version"] >= 1
    assert backup_result["row_counts"]["participant_sessions"] >= 1
    assert backup_result["row_counts"]["trial_summary_logs"] >= 1

    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    destroy_res = researcher.post(f"/admin/api/v1/runs/{run_id}/close", json={"confirm_run_id": run_id})
    assert destroy_res.status_code == 200
    researcher.app.state.store.execute("DELETE FROM trial_summary_logs", ())
    researcher.app.state.store.execute("DELETE FROM trial_event_logs", ())

    restore_result = restore_database(db_target=db_path, backup_path=str(backup_path), confirm_destructive=True)
    assert restore_result["restored_counts"]["trial_summary_logs"] >= 1
    assert restore_result["restored_counts"]["trial_event_logs"] >= 1

    participant_after_restart = TestClient(create_participant_app(db_path))
    exported = participant_after_restart.get(f"/api/v1/exports/sessions/{session_id}")
    assert exported.status_code == 200
    payload = exported.json()
    assert "human_response" in payload["trial_summary_csv"]
    assert payload["raw_event_log_jsonl"].strip()


def test_restore_rejects_invalid_format(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    _seed_minimal_run(db_path)
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps({"backup_format_version": 999, "tables": {}}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="Unsupported backup format version"):
        restore_database(db_target=db_path, backup_path=str(invalid_path), confirm_destructive=True)


def test_restore_requires_explicit_destructive_confirmation(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    _seed_minimal_run(db_path)
    backup_path = tmp_path / "backup.json"
    backup_database(db_target=db_path, output_path=str(backup_path))

    with pytest.raises(RuntimeError, match="Restore is destructive"):
        restore_database(db_target=db_path, backup_path=str(backup_path), confirm_destructive=False)
