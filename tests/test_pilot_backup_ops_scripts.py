from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.researcher_api.main import create_app as create_researcher_app
from scripts.pilot_backup_rotate import apply_retention, build_backup_name, list_backups, run_rotation
from scripts.pilot_restore_drill import run_restore_drill


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _seed_minimal_run(tmp_db: str) -> None:
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
            "config": {"mode": "backup-test", "n_blocks": 1},
            "stimulus_set_ids": [upload.json()["stimulus_set_id"]],
        },
    )
    assert run.status_code == 200
    assert researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate").status_code == 200

    session = participant.post("/api/v1/sessions", json={"run_slug": run.json()["public_slug"]})
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
            "self_confidence": 3,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
        },
    )
    assert submit.status_code == 200


def test_backup_rotation_naming_and_retention(tmp_path: Path) -> None:
    db_path = str(tmp_path / "pilot.sqlite3")
    _seed_minimal_run(db_path)
    backup_dir = tmp_path / "backups"

    run_rotation(
        db_target=db_path,
        backup_dir=backup_dir,
        timestamp_utc="20260101T000001Z",
        retain_count=2,
    )
    run_rotation(
        db_target=db_path,
        backup_dir=backup_dir,
        timestamp_utc="20260101T000002Z",
        retain_count=2,
    )
    result = run_rotation(
        db_target=db_path,
        backup_dir=backup_dir,
        timestamp_utc="20260101T000003Z",
        retain_count=2,
    )

    assert result["retained_count"] == 2
    retained_names = [Path(path).name for path in result["retained_paths"]]
    assert retained_names == [
        build_backup_name(timestamp_utc="20260101T000002Z"),
        build_backup_name(timestamp_utc="20260101T000003Z"),
    ]
    assert Path(result["deleted_paths"][0]).name == build_backup_name(timestamp_utc="20260101T000001Z")


def test_list_backups_ignores_nonconforming_names(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True)
    (backup_dir / "pilot_backup_20260101T010101Z.json").write_text("{}", encoding="utf-8")
    (backup_dir / "pilot_backup_latest.json").write_text("{}", encoding="utf-8")
    (backup_dir / "not_a_backup.txt").write_text("{}", encoding="utf-8")

    found = [path.name for path in list_backups(backup_dir)]
    assert found == ["pilot_backup_20260101T010101Z.json"]


def test_apply_retention_requires_positive_count(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True)
    try:
        apply_retention(backup_dir=backup_dir, retain_count=0)
    except RuntimeError as exc:
        assert "retain-count" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for retain_count=0")


def test_restore_drill_verifies_row_count_parity(tmp_path: Path) -> None:
    db_path = str(tmp_path / "pilot.sqlite3")
    _seed_minimal_run(db_path)
    backup_dir = tmp_path / "backups"

    report = run_restore_drill(
        db_target=db_path,
        backup_dir=backup_dir,
        timestamp_utc="20260101T020202Z",
    )
    assert report["verification_ok"] is True
    assert report["baseline_row_counts"] == report["restored_counts"]
