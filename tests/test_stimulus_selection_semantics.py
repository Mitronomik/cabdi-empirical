from __future__ import annotations

from fastapi.testclient import TestClient

from app.researcher_api.main import create_app


def _login(client: TestClient) -> None:
    assert client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"}).status_code == 200


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
    upload = client.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", ("\n".join(rows) + "\n"), "application/json")},
        data={"name": name, "source_format": "jsonl"},
    )
    assert upload.status_code == 200
    return upload.json()["stimulus_set_id"]


def test_single_select_run_rejects_multiple_main_banks(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "semantics.sqlite3")))
    _login(client)
    set_a = _upload_set(client, name="bank_a", n_items=6)
    set_b = _upload_set(client, name="bank_b", n_items=48)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "single-invalid",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [set_a, set_b],
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 400
    assert "exactly one main stimulus_set_id" in create.json()["detail"]


def test_multi_select_requires_explicit_aggregation_mode(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "semantics.sqlite3")))
    _login(client)
    set_a = _upload_set(client, name="bank_a", n_items=6)
    set_b = _upload_set(client, name="bank_b", n_items=48)

    implicit = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "implicit-aggregation",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [set_a, set_b],
        },
    )
    assert implicit.status_code == 400

    explicit = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "explicit-aggregation",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [set_a, set_b],
            "aggregation_mode": "multi",
        },
    )
    assert explicit.status_code == 200
    assert explicit.json()["aggregation_mode"] == "multi"
    assert explicit.json()["run_summary"]["total_main_items"] == 54


def test_create_run_rejects_practice_main_stimulus_overlap(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "semantics.sqlite3")))
    _login(client)
    set_a = _upload_set(client, name="bank_a", n_items=6)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "practice-main-overlap",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [set_a],
            "practice_stimulus_set_id": set_a,
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 400
    assert "practice_stimulus_set_id must not overlap with main stimulus_set_ids" in create.json()["detail"]


def test_create_run_requires_main_bank_even_when_practice_bank_selected(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "semantics.sqlite3")))
    _login(client)
    practice_set = _upload_set(client, name="practice_bank", n_items=6)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "practice-only-invalid",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [],
            "practice_stimulus_set_id": practice_set,
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 400
    assert (
        "at least one main stimulus_set_id is required; practice_stimulus_set_id is optional and supplementary only"
        in create.json()["detail"]
    )


def test_run_preview_returns_backend_canonical_counts_and_launchability(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "semantics.sqlite3")))
    _login(client)
    set_a = _upload_set(client, name="main_bank", n_items=6)
    practice_set = _upload_set(client, name="practice_bank", n_items=2)

    preview = client.post(
        "/admin/api/v1/runs/preview",
        json={
            "run_name": "preview-only",
            "experiment_id": "toy_v1",
            "task_family": None,
            "config": {"mode": "test"},
            "stimulus_set_ids": [set_a],
            "practice_stimulus_set_id": practice_set,
            "aggregation_mode": "single",
            "notes": "preview",
        },
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["resolved_task_family"] == "scam_detection"
    assert body["practice_item_count"] == 2
    assert body["main_item_count"] == 6
    assert body["expected_trial_count"] == 8
    assert body["validation_errors"] == []
    assert body["launchability_preview"]["launchable"] is True
    assert body["payload_schema_compatibility"]["compatible"] is True
    assert body["selection_summary"]["task_family_field_state"] == "resolved"
    assert body["selection_summary"]["task_family_field_value"] == "scam_detection"
    assert body["selection_summary"]["main_bank_summary_label"] == "main_bank (6)"


def test_create_run_accepts_derivable_task_family_via_shared_preview_core(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "semantics.sqlite3")))
    _login(client)
    set_a = _upload_set(client, name="main_bank", n_items=6)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "derive-task-family",
            "experiment_id": "toy_v1",
            "task_family": None,
            "config": {"mode": "test"},
            "stimulus_set_ids": [set_a],
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    assert create.json()["task_family"] == "scam_detection"
