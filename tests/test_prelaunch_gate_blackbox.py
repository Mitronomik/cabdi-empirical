from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import httpx

from scripts.pilot_prelaunch_gate import run_prelaunch_gate


def _wait_ready(url: str, path: str, ok_codes: set[int], timeout: float = 25.0) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            res = httpx.get(f"{url}{path}", timeout=3.0)
            if res.status_code in ok_codes:
                return
            last = f"status={res.status_code}"
        except Exception as exc:
            last = str(exc)
        time.sleep(0.5)
    raise AssertionError(f"service not ready: {url}{path} ({last})")


def _bootstrap_active_run_over_http(researcher_base_url: str) -> str:
    with httpx.Client(base_url=researcher_base_url, timeout=20.0) as researcher:
        login = researcher.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
        assert login.status_code == 200
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
                "config": {"mode": "prelaunch-gate-blackbox-test"},
                "stimulus_set_ids": [upload.json()["stimulus_set_id"]],
            },
        )
        assert run.status_code == 200
        run_id = run.json()["run_id"]
        activate = researcher.post(f"/admin/api/v1/runs/{run_id}/activate")
        assert activate.status_code == 200
        return run.json()["public_slug"]


def test_prelaunch_gate_blackbox_http_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "pilot.sqlite3"
    participant_base_url = "http://127.0.0.1:18080"
    researcher_base_url = "http://127.0.0.1:18081"
    env = {**os.environ, "PILOT_DB_PATH": str(db_path), "PILOT_RESEARCHER_PASSWORD": "admin1234"}

    participant_proc = subprocess.Popen(
        [
            "python",
            "-m",
            "uvicorn",
            "app.participant_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "18080",
        ],
        env=env,
    )
    researcher_proc = subprocess.Popen(
        [
            "python",
            "-m",
            "uvicorn",
            "app.researcher_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "18081",
        ],
        env=env,
    )

    try:
        _wait_ready(participant_base_url, "/health", {200})
        _wait_ready(researcher_base_url, "/admin/api/v1/auth/me", {401})
        run_slug = _bootstrap_active_run_over_http(researcher_base_url)
        report = run_prelaunch_gate(
            db_target=str(db_path),
            run_slug=run_slug,
            output_dir=tmp_path / "gate_blackbox",
            researcher_username="admin",
            researcher_password="admin1234",
            require_postgres=False,
            run_restore_drill=False,
            allow_restore_drill_skip=True,
            participant_base_url=participant_base_url,
            researcher_base_url=researcher_base_url,
        )
    finally:
        participant_proc.terminate()
        researcher_proc.terminate()
        participant_proc.wait(timeout=10)
        researcher_proc.wait(timeout=10)

    assert report["launch_ready"] is True
    by_id = {entry["check_id"]: entry for entry in report["checks"]}
    assert by_id["launch_boundary_mode"]["detail"] == "black-box HTTP boundary mode enabled"
    assert by_id["blackbox_launch_realism_mode"]["passed"] is True
    assert by_id["http_stack_readiness"]["passed"] is True
    assert by_id["public_private_surface_boundary"]["passed"] is True
    assert by_id["researcher_cookie_persistence"]["passed"] is True
    assert by_id["researcher_protected_boundary"]["passed"] is True
    assert by_id["session_progress_resume_final_submit"]["passed"] is True
    assert by_id["participant_bilingual_path_readiness"]["passed"] is True
    assert by_id["researcher_cabinet_operational_readiness"]["passed"] is True
    assert by_id["diagnostics_retrieval"]["passed"] is True
    assert by_id["export_retrieval"]["passed"] is True
