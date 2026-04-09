from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from app.researcher_api.main import create_app


def _login(client: TestClient) -> None:
    assert client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"}).status_code == 200


def _upload_set(client: TestClient, *, name: str, task_family: str = "scam_detection", n_items: int = 4) -> str:
    rows = []
    for idx in range(n_items):
        rows.append(
            (
                '{"stimulus_id":"%s","task_family":"%s","content_type":"text",'
                '"payload":{"title":"Case","body":"%s"},"true_label":"scam","difficulty_prior":"low",'
                '"model_prediction":"scam","model_confidence":"high","model_correct":true,"eligible_sets":["demo"]}'
            )
            % (f"{name}_{idx+1}", task_family, idx + 1)
        )
    upload = client.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", ("\n".join(rows) + "\n"), "application/json")},
        data={"name": name, "source_format": "jsonl"},
    )
    assert upload.status_code == 200
    return upload.json()["stimulus_set_id"]


def test_run_summary_includes_per_bank_and_total_counts(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "summary.sqlite3")))
    _login(client)
    set_a = _upload_set(client, name="bank_a", n_items=6)
    set_b = _upload_set(client, name="bank_b", n_items=48)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "summary-run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [set_a, set_b],
            "aggregation_mode": "multi",
        },
    )
    assert create.status_code == 200
    summary = create.json()["run_summary"]
    assert len(summary["banks"]) == 2
    assert summary["total_main_items"] == 54
    assert summary["expected_trial_count"] == 54


def test_run_summary_single_main_bank_expected_count_equals_selected_bank_size(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "summary.sqlite3")))
    _login(client)
    set_a = _upload_set(client, name="bank_a", n_items=6)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "summary-run-single",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [set_a],
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    run_id = create.json()["run_id"]
    details = client.get(f"/admin/api/v1/runs/{run_id}")
    assert details.status_code == 200
    summary = details.json()["run_summary"]
    assert summary["main_item_count"] == 6
    assert summary["practice_item_count"] == 0
    assert summary["expected_trial_count"] == 6


def test_run_summary_single_select_does_not_include_unselected_main_bank(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "summary.sqlite3")))
    _login(client)
    selected_main = _upload_set(client, name="selected_main", n_items=6)
    _upload_set(client, name="other_main", n_items=48)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "summary-run-single-protection",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [selected_main],
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    summary = create.json()["run_summary"]
    assert summary["main_item_count"] == 6
    assert summary["expected_trial_count"] == 6


def test_run_summary_practice_plus_main_expected_count_is_sum(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "summary.sqlite3")))
    _login(client)
    main_set = _upload_set(client, name="main_set", n_items=48)
    practice_set = _upload_set(client, name="practice_set", n_items=6)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "summary-run-practice-main",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [main_set],
            "practice_stimulus_set_id": practice_set,
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    summary = create.json()["run_summary"]
    assert summary["practice_item_count"] == 6
    assert summary["main_item_count"] == 48
    assert summary["expected_trial_count"] == 54


def test_run_summary_counts_align_across_create_details_and_list_surfaces(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "summary.sqlite3")))
    _login(client)
    main_set = _upload_set(client, name="main_set", n_items=8)
    practice_set = _upload_set(client, name="practice_set", n_items=3)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "summary-alignment-run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [main_set],
            "practice_stimulus_set_id": practice_set,
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    created_summary = create.json()["run_summary"]
    run_id = create.json()["run_id"]

    details = client.get(f"/admin/api/v1/runs/{run_id}")
    assert details.status_code == 200
    details_summary = details.json()["run_summary"]

    listed = client.get("/admin/api/v1/runs")
    assert listed.status_code == 200
    list_summary = next(item["run_summary"] for item in listed.json() if item["run_id"] == run_id)

    assert created_summary["practice_item_count"] == 3
    assert created_summary["main_item_count"] == 8
    assert created_summary["expected_trial_count"] == 11
    assert details_summary["expected_trial_count"] == created_summary["expected_trial_count"]
    assert list_summary["expected_trial_count"] == created_summary["expected_trial_count"]
    assert details_summary["practice_item_count"] == created_summary["practice_item_count"]
    assert list_summary["main_item_count"] == created_summary["main_item_count"]


def test_activation_blocked_for_invalid_selection(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "summary.sqlite3")))
    _login(client)
    good_set = _upload_set(client, name="bank_good", task_family="scam_detection")
    incompatible = _upload_set(client, name="bank_other_family", task_family="scam_not_scam")

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "bad-run",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [good_set, incompatible],
            "aggregation_mode": "multi",
        },
    )
    assert create.status_code == 400
    assert "match run task_family" in create.json()["detail"]


def test_activation_rejects_practice_main_overlap_if_invalid_row_exists(tmp_path) -> None:
    db_path = tmp_path / "summary.sqlite3"
    client = TestClient(create_app(str(db_path)))
    _login(client)
    main_set = _upload_set(client, name="main_set", n_items=8)
    practice_set = _upload_set(client, name="practice_set", n_items=3)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "overlap-defensive-validation",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"mode": "test"},
            "stimulus_set_ids": [main_set],
            "practice_stimulus_set_id": practice_set,
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    run_id = create.json()["run_id"]

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE researcher_runs SET stimulus_set_ids_json = ?, practice_stimulus_set_id = ? WHERE run_id = ?",
            (json.dumps([main_set]), main_set, run_id),
        )
        conn.commit()

    activate = client.post(f"/admin/api/v1/runs/{run_id}/activate")
    assert activate.status_code == 400
    assert "practice_stimulus_set_id must not overlap with main stimulus_set_ids" in activate.json()["detail"]


def test_activation_rejects_run_that_would_create_empty_main_blocks(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "summary.sqlite3")))
    _login(client)
    main_set = _upload_set(client, name="main-too-small", n_items=2)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "empty-main-blocks-rejected",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"execution": {"n_blocks": 3, "trials_per_block": 2, "practice_trials": 0}},
            "stimulus_set_ids": [main_set],
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    run_id = create.json()["run_id"]

    activate = client.post(f"/admin/api/v1/runs/{run_id}/activate")
    assert activate.status_code == 400
    assert "run has insufficient main items for configured block design" in activate.json()["detail"]
    assert "main_item_count=2, n_blocks=3" in activate.json()["detail"]


def test_draft_run_details_and_list_surface_canonical_launchability_error_before_activation(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "summary.sqlite3")))
    _login(client)
    main_set = _upload_set(client, name="main-too-small-reporting", n_items=2)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "empty-main-blocks-preflight-visible",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"execution": {"n_blocks": 3, "trials_per_block": 2, "practice_trials": 0}},
            "stimulus_set_ids": [main_set],
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    run_id = create.json()["run_id"]

    details = client.get(f"/admin/api/v1/runs/{run_id}")
    assert details.status_code == 200
    assert "run has insufficient main items for configured block design" in details.json()["launchability_reason"]
    assert "main_item_count=2, n_blocks=3" in details.json()["launchability_reason"]

    listed = client.get("/admin/api/v1/runs")
    assert listed.status_code == 200
    listed_row = next(item for item in listed.json() if item["run_id"] == run_id)
    assert listed_row["launchability_reason"] == details.json()["launchability_reason"]


def test_valid_draft_run_reason_requires_activation_without_fabricated_validation_error(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "summary.sqlite3")))
    _login(client)
    main_set = _upload_set(client, name="main-valid-draft", n_items=3)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "valid-draft-reason",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"execution": {"n_blocks": 3, "trials_per_block": 2, "practice_trials": 0}},
            "stimulus_set_ids": [main_set],
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    run_id = create.json()["run_id"]

    details = client.get(f"/admin/api/v1/runs/{run_id}")
    assert details.status_code == 200
    assert details.json()["launchability_reason"] == "run is draft; activate to accept new participant sessions"


def test_activation_allows_exactly_one_main_trial_per_block_boundary(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "summary.sqlite3")))
    _login(client)
    main_set = _upload_set(client, name="main-boundary", n_items=3)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "non-empty-main-blocks-boundary",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"execution": {"n_blocks": 3, "trials_per_block": 2, "practice_trials": 0}},
            "stimulus_set_ids": [main_set],
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    run_id = create.json()["run_id"]

    activate = client.post(f"/admin/api/v1/runs/{run_id}/activate")
    assert activate.status_code == 200


def test_activation_allows_uneven_but_non_empty_main_block_distribution(tmp_path) -> None:
    client = TestClient(create_app(str(tmp_path / "summary.sqlite3")))
    _login(client)
    main_set = _upload_set(client, name="main-uneven", n_items=5)

    create = client.post(
        "/admin/api/v1/runs",
        json={
            "run_name": "non-empty-main-blocks-uneven",
            "experiment_id": "toy_v1",
            "task_family": "scam_detection",
            "config": {"execution": {"n_blocks": 3, "trials_per_block": 2, "practice_trials": 0}},
            "stimulus_set_ids": [main_set],
            "aggregation_mode": "single",
        },
    )
    assert create.status_code == 200
    run_id = create.json()["run_id"]

    activate = client.post(f"/admin/api/v1/runs/{run_id}/activate")
    assert activate.status_code == 200
