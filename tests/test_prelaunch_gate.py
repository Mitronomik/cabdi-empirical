from __future__ import annotations

from fastapi.testclient import TestClient

from app.researcher_api.main import create_app as create_researcher_app
from scripts.pilot_prelaunch_gate import run_prelaunch_gate


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _bootstrap_active_run(db_path: str) -> str:
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)

    payload = (
        '{"stimulus_id":"s1","task_family":"scam_detection","content_type":"text","payload":{"title":"Case 1","body":"a"},'
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
            "run_name": "gate run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "prelaunch-gate-test"},
            "stimulus_set_ids": [upload.json()["stimulus_set_id"]],
        },
    )
    assert run.status_code == 200
    run_id = run.json()["run_id"]
    activate = researcher.post(f"/admin/api/v1/runs/{run_id}/activate")
    assert activate.status_code == 200
    return run.json()["public_slug"]


def test_prelaunch_gate_fails_without_active_run(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    output_dir = tmp_path / "gate_out"

    report = run_prelaunch_gate(
        db_target=db_path,
        run_slug="missing-run",
        output_dir=output_dir,
        researcher_username="admin",
        researcher_password="admin1234",
        require_postgres=False,
        require_blackbox_http=False,
        allow_restore_drill_skip=True,
        run_restore_drill=False,
        concurrent_sessions=2,
        concurrent_trials_per_session=1,
    )

    assert report["launch_ready"] is False
    blocker_ids = {entry["check_id"] for entry in report["blocking_failures"]}
    assert "active_run_present" in blocker_ids
    assert (output_dir / "prelaunch_gate_report.json").exists()
    assert (output_dir / "prelaunch_gate_checklist.md").exists()


def test_prelaunch_gate_passes_full_integrity_path_with_restore_drill(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    run_slug = _bootstrap_active_run(db_path)
    output_dir = tmp_path / "gate_ok"

    report = run_prelaunch_gate(
        db_target=db_path,
        run_slug=run_slug,
        output_dir=output_dir,
        researcher_username="admin",
        researcher_password="admin1234",
        require_postgres=False,
        require_blackbox_http=False,
        run_restore_drill=True,
        concurrent_sessions=3,
        concurrent_trials_per_session=2,
    )

    assert report["launch_ready"] is True
    assert report["blocking_failures"] == []
    by_id = {entry["check_id"]: entry for entry in report["checks"]}
    assert by_id["participant_public_slug_entry"]["passed"] is True
    assert by_id["public_private_surface_boundary"]["passed"] is True
    assert by_id["researcher_auth"]["passed"] is True
    assert by_id["researcher_protected_boundary"]["passed"] is True
    assert by_id["session_progress_resume_final_submit"]["passed"] is True
    assert by_id["concurrent_session_smoke"]["passed"] is True
    assert by_id["participant_bilingual_path_readiness"]["passed"] is True
    assert by_id["researcher_cabinet_operational_readiness"]["passed"] is True
    assert by_id["diagnostics_retrieval"]["passed"] is True
    assert by_id["export_retrieval"]["passed"] is True
    assert by_id["analysis_ready_outputs"]["passed"] is True
    assert by_id["backup_configured"]["passed"] is True
    assert by_id["backup_restore_drill"]["passed"] is True


def test_prelaunch_gate_boundary_failure_is_diagnostic(tmp_path, monkeypatch):
    db_path = str(tmp_path / "pilot.sqlite3")
    run_slug = _bootstrap_active_run(db_path)

    def _fake_boundary(*, participant_client, unauth_researcher_client):
        return (
            False,
            "public/private contour probe (participant health=200, participant admin probe=200, researcher docs=200, researcher openapi=200, researcher unauth protected=200)",
            {
                "participant_health": 200,
                "participant_admin_probe": 200,
                "researcher_docs": 200,
                "researcher_openapi": 200,
                "researcher_protected": 200,
            },
        )

    monkeypatch.setattr("scripts.pilot_prelaunch_gate._check_surface_boundary", _fake_boundary)
    report = run_prelaunch_gate(
        db_target=db_path,
        run_slug=run_slug,
        output_dir=tmp_path / "gate_boundary_failure",
        researcher_username="admin",
        researcher_password="admin1234",
        require_postgres=False,
        require_blackbox_http=False,
        run_restore_drill=False,
        allow_restore_drill_skip=True,
    )

    assert report["launch_ready"] is False
    by_id = {entry["check_id"]: entry for entry in report["checks"]}
    assert by_id["public_private_surface_boundary"]["passed"] is False
    assert by_id["public_private_surface_boundary"]["metadata"]["researcher_docs"] == 200
    blocker_ids = {entry["check_id"] for entry in report["blocking_failures"]}
    assert "public_private_surface_boundary" in blocker_ids


def test_prelaunch_gate_blocks_when_postgres_required_but_sqlite_target(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    run_slug = _bootstrap_active_run(db_path)

    report = run_prelaunch_gate(
        db_target=db_path,
        run_slug=run_slug,
        output_dir=tmp_path / "gate_postgres_required",
        researcher_username="admin",
        researcher_password="admin1234",
        require_postgres=True,
        require_blackbox_http=False,
        run_restore_drill=True,
        concurrent_sessions=2,
        concurrent_trials_per_session=1,
    )

    assert report["launch_ready"] is False
    blocker_ids = {entry["check_id"] for entry in report["blocking_failures"]}
    assert "staging_postgres_posture" in blocker_ids


def test_prelaunch_gate_blocks_when_restore_drill_skipped_without_override(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    run_slug = _bootstrap_active_run(db_path)

    report = run_prelaunch_gate(
        db_target=db_path,
        run_slug=run_slug,
        output_dir=tmp_path / "gate_restore_skip_blocked",
        researcher_username="admin",
        researcher_password="admin1234",
        require_postgres=False,
        require_blackbox_http=False,
        run_restore_drill=False,
    )

    assert report["launch_ready"] is False
    blocker_ids = {entry["check_id"] for entry in report["blocking_failures"]}
    assert "backup_restore_drill" in blocker_ids
