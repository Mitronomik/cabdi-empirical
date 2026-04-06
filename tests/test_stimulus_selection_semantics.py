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

