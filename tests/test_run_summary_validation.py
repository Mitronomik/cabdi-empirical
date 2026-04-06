from __future__ import annotations

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
    assert summary["expected_trial_count"] > 0


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

