from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.participant_api.persistence.postgres_store import PostgresStore
from app.participant_api.persistence.sqlite_store import SQLiteStore
from app.participant_api.persistence.store_factory import create_store
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert res.status_code == 200


def test_store_factory_defaults_to_sqlite() -> None:
    store = create_store("pilot/sessions/test.sqlite3")
    assert isinstance(store, SQLiteStore)


def test_store_factory_selects_postgres_from_url() -> None:
    dsn = "postgresql://pilot:pilot@localhost:5432/cabdi"
    try:
        store = create_store(dsn)
    except RuntimeError as exc:  # pragma: no cover - environment without psycopg
        if "psycopg" in str(exc):
            pytest.skip("psycopg is not installed in this environment")
        raise
    assert isinstance(store, PostgresStore)


@pytest.mark.skipif(not os.getenv("PILOT_TEST_POSTGRES_DSN"), reason="PILOT_TEST_POSTGRES_DSN not set")
def test_postgres_backend_end_to_end_parity_flow() -> None:
    base_dsn = os.environ["PILOT_TEST_POSTGRES_DSN"]
    schema = f"test_pr12_{uuid.uuid4().hex[:10]}"
    setup_store = PostgresStore(base_dsn)
    with setup_store.connect() as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    scoped_dsn = f"{base_dsn}?options=-csearch_path%3D{schema}"
    try:
        researcher = TestClient(create_researcher_app(scoped_dsn))
        _login_researcher(researcher)
        participant = TestClient(create_participant_app(scoped_dsn))
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
                "run_name": "postgres run",
                "experiment_id": "toy_v1",
                "task_family": "scam_detection",
                "config": {"mode": "test"},
                "stimulus_set_ids": [upload.json()["stimulus_set_id"]],
            },
        )
        assert run.status_code == 200
        assert researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate").status_code == 200

        session = participant.post(
            "/api/v1/sessions",
            json={"run_slug": run.json()["public_slug"]},
        )
        assert session.status_code == 200
        session_id = session.json()["session_id"]
        assert participant.post(f"/api/v1/sessions/{session_id}/start").status_code == 200

        next_trial = participant.get(f"/api/v1/sessions/{session_id}/next-trial")
        assert next_trial.status_code == 200
        trial_payload = next_trial.json()
        submit = participant.post(
            f"/api/v1/sessions/{session_id}/trials/{trial_payload['trial_id']}/submit",
            json={
                "human_response": trial_payload["stimulus"]["true_label"],
                "reaction_time_ms": 900,
                "self_confidence": 65,
                "reason_clicked": False,
                "evidence_opened": False,
                "verification_completed": False,
            },
        )
        assert submit.status_code == 200

        diagnostics = researcher.get(f"/admin/api/v1/runs/{run.json()['run_id']}/diagnostics")
        assert diagnostics.status_code == 200
        exports = researcher.get(f"/admin/api/v1/runs/{run.json()['run_id']}/exports")
        assert exports.status_code == 200
    finally:
        cleanup_store = PostgresStore(base_dsn)
        with cleanup_store.connect() as conn:
            conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
