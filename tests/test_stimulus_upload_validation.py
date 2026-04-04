from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.researcher_api.main import create_app


def _client(tmp_path):
    app = create_app(str(tmp_path / "pilot.sqlite3"))
    return TestClient(app)


def _base_item(**overrides):
    item = {
        "stimulus_id": "s1",
        "task_family": "scam_detection",
        "content_type": "text",
        "payload": {"title": "Email alert", "body": "Verify account now"},
        "true_label": "scam",
        "difficulty_prior": "low",
        "model_prediction": "scam",
        "model_confidence": "high",
        "model_correct": True,
        "eligible_sets": ["demo"],
    }
    item.update(overrides)
    return item


def _upload(client: TestClient, rows: list[dict]):
    payload = "\n".join(json.dumps(r) for r in rows) + "\n"
    return client.post(
        "/admin/api/v1/stimuli/upload",
        files={"file": ("stimuli.jsonl", payload, "application/json")},
        data={"name": "demo_set", "source_format": "jsonl"},
    )


def test_stimulus_upload_jsonl_success_returns_contract_metadata(tmp_path):
    client = _client(tmp_path)
    res = _upload(client, [_base_item()])
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["validation_status"] == "valid"
    assert body["n_items"] == 1
    assert body["payload_schema_version"] == "stimulus_payload.v1"
    assert body["preview_rows"][0]["payload"]["body"] == "Verify account now"


def test_stimulus_upload_rejects_malformed_required_fields(tmp_path):
    client = _client(tmp_path)
    bad = _base_item(payload={"title": "Missing body"})
    res = _upload(client, [bad])
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert body["validation_status"] == "invalid"
    assert any(e["code"] == "missing_payload_body" for e in body["errors"])


def test_duplicate_stimulus_id_rejected(tmp_path):
    client = _client(tmp_path)
    row = _base_item()
    res = _upload(client, [row, row])
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert any(e["code"] == "duplicate_stimulus_id" for e in body["errors"])


def test_legacy_payload_is_normalized_when_resolvable(tmp_path):
    client = _client(tmp_path)
    legacy_row = _base_item(payload={"title": "Legacy", "message": "Legacy body"})
    res = _upload(client, [legacy_row])
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["validation_status"] == "warning_only"
    assert any(w["code"] == "legacy_payload_normalized" for w in body["warnings"])

    detail = client.get(f"/admin/api/v1/stimuli/{body['stimulus_set_id']}")
    assert detail.status_code == 200
    assert detail.json()["items"][0]["payload"]["body"] == "Legacy body"


def test_unresolved_legacy_normalization_fails(tmp_path):
    client = _client(tmp_path)
    ambiguous_row = _base_item(payload={"title": "Ambiguous", "message": "m", "scenario": "s"})
    res = _upload(client, [ambiguous_row])
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert any(e["code"] == "ambiguous_legacy_payload" for e in body["errors"])


def test_incompatible_task_family_or_renderer_is_flagged(tmp_path):
    client = _client(tmp_path)
    bad_task = _base_item(task_family="unsupported_task")
    res = _upload(client, [bad_task])
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert any(e["code"] == "invalid_task_family" for e in body["errors"])

    bad_renderer = _base_item(content_type="audio")
    res2 = _upload(client, [bad_renderer])
    assert res2.status_code == 200
    assert any(e["code"] == "invalid_content_type" for e in res2.json()["errors"])
