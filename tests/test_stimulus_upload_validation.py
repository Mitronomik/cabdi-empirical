from __future__ import annotations

from fastapi.testclient import TestClient

from app.researcher_api.main import create_app


def _client(tmp_path):
    app = create_app(str(tmp_path / "pilot.sqlite3"))
    return TestClient(app)


def test_stimulus_upload_jsonl_success(tmp_path):
    client = _client(tmp_path)
    payload = (
        '{"stimulus_id":"s1","task_family":"scam_detection","content_type":"text","payload":{"text":"a"},'
        '"true_label":"scam","difficulty_prior":"low","model_prediction":"scam","model_confidence":"high",'
        '"model_correct":true,"eligible_sets":["demo"]}\n'
    )
    res = client.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", payload, "application/json")},
        data={"name": "demo_set", "source_format": "jsonl"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["n_items"] == 1


def test_stimulus_upload_validation_error(tmp_path):
    client = _client(tmp_path)
    bad_payload = '{"stimulus_id":"s1","task_family":"scam_detection"}\n'
    res = client.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", bad_payload, "application/json")},
        data={"name": "bad_set", "source_format": "jsonl"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert body["errors"]
