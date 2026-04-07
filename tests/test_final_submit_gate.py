from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    assert client.post('/admin/api/v1/auth/login', json={'username': 'admin', 'password': 'admin1234'}).status_code == 200


def _bootstrap_run(tmp_path) -> tuple[TestClient, str]:
    db_path = str(tmp_path / 'pilot_api.sqlite3')
    participant = TestClient(create_app(db_path))
    researcher = TestClient(create_researcher_app(db_path))
    _login_researcher(researcher)
    payload = (
        '{"stimulus_id":"s1","task_family":"scam_detection","content_type":"text","payload":{"title":"Case","body":"a"},'
        '"true_label":"scam","difficulty_prior":"low","model_prediction":"scam","model_confidence":"high",'
        '"model_correct":true,"eligible_sets":["demo"]}\n'
    )
    upload = researcher.post(
        '/admin/api/v1/stimuli/upload',
        files={'file': ('stimuli.jsonl', payload, 'application/json')},
        data={'name': 'set1', 'source_format': 'jsonl'},
    )
    run = researcher.post(
        '/admin/api/v1/runs',
        json={
            'run_name': 'final-submit-run',
            'experiment_id': 'toy_v1',
            'task_family': 'scam_detection',
            'config': {'mode': 'test'},
            'stimulus_set_ids': [upload.json()['stimulus_set_id']],
        },
    )
    assert researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate").status_code == 200
    return participant, run.json()['public_slug']


def _finish_required_work(client: TestClient, session_id: str) -> None:
    while True:
        next_res = client.get(f'/api/v1/sessions/{session_id}/next-trial')
        if next_res.status_code == 409:
            block_id = next_res.json()['detail']['block_id']
            assert client.post(
                f'/api/v1/sessions/{session_id}/blocks/{block_id}/questionnaire',
                json={'burden': 10, 'trust': 20, 'usefulness': 30},
            ).status_code == 200
            continue
        body = next_res.json()
        if body.get('status') == 'awaiting_final_submit':
            return
        assert client.post(
            f"/api/v1/sessions/{session_id}/trials/{body['trial_id']}/submit",
            json={
                'human_response': body['stimulus']['true_label'],
                'reaction_time_ms': 1000,
                'self_confidence': 3,
                'reason_clicked': False,
                'evidence_opened': False,
                'verification_completed': False,
            },
        ).status_code == 200


def test_session_not_terminal_before_explicit_final_submit(tmp_path) -> None:
    client, run_slug = _bootstrap_run(tmp_path)
    created = client.post('/api/v1/sessions', json={'run_slug': run_slug}).json()
    session_id = created['session_id']
    assert client.post(f'/api/v1/sessions/{session_id}/start').status_code == 200

    _finish_required_work(client, session_id)
    progress = client.get(f'/api/v1/sessions/{session_id}/progress').json()
    assert progress['status'] == 'awaiting_final_submit'


def test_final_submit_transitions_to_finalized(tmp_path) -> None:
    client, run_slug = _bootstrap_run(tmp_path)
    created = client.post('/api/v1/sessions', json={'run_slug': run_slug}).json()
    session_id = created['session_id']
    assert client.post(f'/api/v1/sessions/{session_id}/start').status_code == 200

    _finish_required_work(client, session_id)
    submitted = client.post(f'/api/v1/sessions/{session_id}/final-submit')
    assert submitted.status_code == 200
    assert submitted.json()['status'] == 'finalized'

    progress = client.get(f'/api/v1/sessions/{session_id}/progress').json()
    assert progress['status'] == 'finalized'
    assert progress['finalized_at'] is not None


def test_repeated_final_submit_does_not_mutate_answers(tmp_path) -> None:
    client, run_slug = _bootstrap_run(tmp_path)
    created = client.post('/api/v1/sessions', json={'run_slug': run_slug}).json()
    session_id = created['session_id']
    assert client.post(f'/api/v1/sessions/{session_id}/start').status_code == 200

    _finish_required_work(client, session_id)
    first = client.post(f'/api/v1/sessions/{session_id}/final-submit')
    second = client.post(f'/api/v1/sessions/{session_id}/final-submit')
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()['already_finalized'] is True

    summary_before = client.get(f'/api/v1/exports/sessions/{session_id}').json()['participant_session_summary']['n_trial_summaries']
    summary_after = client.get(f'/api/v1/exports/sessions/{session_id}').json()['participant_session_summary']['n_trial_summaries']
    assert summary_after == summary_before
