from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def _bootstrap_run(researcher: TestClient) -> dict[str, str]:
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
    stimulus_set_id = upload.json()["stimulus_set_id"]
    run_res = researcher.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "run export",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"n_blocks": 1},
            "stimulus_set_ids": [stimulus_set_id],
        },
    )
    activate = researcher.post(f"/admin/api/v1/runs/{run_res.json()['run_id']}/activate")
    assert activate.status_code == 200
    return {"run_id": run_res.json()["run_id"], "run_slug": run_res.json()["public_slug"]}


def test_run_exports_include_expected_sections(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    participant = TestClient(create_participant_app(db_path))

    run_info = _bootstrap_run(researcher)
    create_session = participant.post(
        "/api/v1/sessions",
        json={"run_slug": run_info["run_slug"], "language": "ru"},
    )
    assert create_session.status_code == 200

    exports_res = researcher.get(f"/admin/api/v1/runs/{run_info['run_id']}/exports")
    assert exports_res.status_code == 200
    body = exports_res.json()
    assert "artifacts" in body
    assert "session_summary_json" in body
    assert body["export_state"] == "available"
    assert "available_outputs" in body
    assert body["available_outputs"]["session_summary_csv"] is True
    assert body["available_outputs"]["trial_level_csv"] is False
    assert body["session_summary_json"][0]["language"] == "ru"
    assert "No trial summaries available" in body["warnings"][0]
    assert body["artifact_policy"]["mode"] == "replace_current"
    assert body["manifest_version"] == "pilot_export_manifest.v1"
    assert body["run_scope"]["scope_level"] == "run"
    assert body["artifact_layers"]["source_of_truth_extracts"]
    assert "trial_level_csv" in body["artifact_layers"]["derived_analysis_artifacts"]
    artifact_types = {item["artifact_type"] for item in body["artifacts"]}
    assert "raw_event_log_jsonl" in artifact_types
    assert "trial_level_csv" in artifact_types
    by_type = {item["artifact_type"]: item for item in body["artifacts"]}
    assert by_type["trial_summary_csv"]["data_layer"] == "source_of_truth_extract"
    assert by_type["trial_level_csv"]["data_layer"] == "derived_analysis_artifact"
    manifest = json.loads((Path(body["artifact_root"]) / "manifest.json").read_text(encoding="utf-8"))
    assert "trial_summary_rows" in manifest["completeness"]["incomplete_source_streams"]


def test_run_exports_include_analysis_ready_outputs_when_trial_data_exists(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    participant = TestClient(create_participant_app(db_path))

    run_info = _bootstrap_run(researcher)
    create_session = participant.post(
        "/api/v1/sessions",
        json={"run_slug": run_info["run_slug"], "language": "en"},
    )
    assert create_session.status_code == 200
    session_id = create_session.json()["session_id"]
    assert participant.post(f"/api/v1/sessions/{session_id}/start").status_code == 200
    next_trial = participant.get(f"/api/v1/sessions/{session_id}/next-trial")
    trial_payload = next_trial.json()
    trial_id = trial_payload["trial_id"]
    submit = participant.post(
        f"/api/v1/sessions/{session_id}/trials/{trial_id}/submit",
        json={
            "human_response": trial_payload["stimulus"]["model_prediction"],
            "self_confidence": 2,
            "reaction_time_ms": 1200,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
        },
    )
    assert submit.status_code == 200

    exports_res = researcher.get(f"/admin/api/v1/runs/{run_info['run_id']}/exports")
    assert exports_res.status_code == 200
    body = exports_res.json()
    assert body["available_outputs"]["trial_level_csv"] is True
    assert body["available_outputs"]["participant_summary_csv"] is True
    assert body["available_outputs"]["mixed_effects_ready_csv"] is True
    assert body["available_outputs"]["pilot_summary_md"] is True

    trial_summary_artifact = researcher.get(
        f"/admin/api/v1/runs/{run_info['run_id']}/exports/artifacts/trial_summary_csv"
    )
    assert trial_summary_artifact.status_code == 200
    trial_summary_rows = list(csv.DictReader(io.StringIO(trial_summary_artifact.text)))
    assert trial_summary_rows
    assert trial_summary_rows[0]["run_id"] == run_info["run_id"]
    assert trial_summary_rows[0]["session_id"] == session_id
    assert trial_summary_rows[0]["trial_id"] == trial_id

    trial_level_artifact = researcher.get(
        f"/admin/api/v1/runs/{run_info['run_id']}/exports/artifacts/trial_level_csv"
    )
    assert trial_level_artifact.status_code == 200
    trial_level_rows = list(csv.DictReader(io.StringIO(trial_level_artifact.text)))
    assert trial_level_rows
    assert trial_level_rows[0]["session_id"] == session_id

    manifest_path = Path(body["artifact_root"]) / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == run_info["run_id"]
    assert manifest["manifest_version"] == "pilot_export_manifest.v1"
    assert manifest["scope"]["scope_level"] == "run"
    assert manifest["source_of_truth_counts"]["trial_summary_rows"] >= 1
    assert "trial_summary_csv" in manifest["provenance"]["derived_from_artifacts"]


def test_run_export_generation_replaces_current_artifacts(tmp_path):
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    participant = TestClient(create_participant_app(db_path))

    run_info = _bootstrap_run(researcher)
    participant.post("/api/v1/sessions", json={"run_slug": run_info["run_slug"]})

    first = researcher.get(f"/admin/api/v1/runs/{run_info['run_id']}/exports").json()
    first_manifest = Path(first["artifact_root"]) / "manifest.json"
    first_generated_at = json.loads(first_manifest.read_text(encoding="utf-8"))["generated_at"]

    second = researcher.get(f"/admin/api/v1/runs/{run_info['run_id']}/exports").json()
    second_manifest = Path(second["artifact_root"]) / "manifest.json"
    second_generated_at = json.loads(second_manifest.read_text(encoding="utf-8"))["generated_at"]

    assert first_manifest == second_manifest
    assert first_generated_at != second_generated_at
