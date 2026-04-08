from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    assert client.post('/admin/api/v1/auth/login', json={'username': 'admin', 'password': 'admin1234'}).status_code == 200


def _bootstrap(tmp_path) -> tuple[TestClient, str]:
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
            'run_name': 'incremental run',
            'experiment_id': 'toy_v1',
            'task_family': 'scam_detection',
            'config': {'mode': 'test', 'n_blocks': 1},
            'stimulus_set_ids': [upload.json()['stimulus_set_id']],
        },
    )
    assert researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate").status_code == 200
    return participant, run.json()['public_slug']


def test_progress_survives_reload_after_trial_submit(tmp_path) -> None:
    client, run_slug = _bootstrap(tmp_path)
    created = client.post('/api/v1/sessions', json={'run_slug': run_slug}).json()
    session_id = created['session_id']
    assert client.post(f'/api/v1/sessions/{session_id}/start').status_code == 200

    trial = client.get(f'/api/v1/sessions/{session_id}/next-trial').json()
    submit = client.post(
        f"/api/v1/sessions/{session_id}/trials/{trial['trial_id']}/submit",
        json={
            'human_response': trial['stimulus']['true_label'],
            'reaction_time_ms': 800,
            'self_confidence': 2,
            'reason_clicked': False,
            'evidence_opened': False,
            'verification_completed': False,
        },
    )
    assert submit.status_code == 200
    assert submit.json()['saved_ack']['saved'] is True

    reloaded = TestClient(create_app(str(tmp_path / 'pilot_api.sqlite3')))
    progress = reloaded.get(f'/api/v1/sessions/{session_id}/progress').json()
    assert progress['current_trial_index'] >= 1
    assert progress['last_activity_at'] is not None


def test_progress_survives_reload_after_questionnaire_submit(tmp_path) -> None:
    client, run_slug = _bootstrap(tmp_path)
    created = client.post('/api/v1/sessions', json={'run_slug': run_slug}).json()
    session_id = created['session_id']
    assert client.post(f'/api/v1/sessions/{session_id}/start').status_code == 200

    block_id = None
    while True:
        next_res = client.get(f'/api/v1/sessions/{session_id}/next-trial')
        if next_res.status_code == 409:
            block_id = next_res.json()['detail']['block_id']
            break
        body = next_res.json()
        if body.get('status'):
            continue
        assert client.post(
            f"/api/v1/sessions/{session_id}/trials/{body['trial_id']}/submit",
            json={
                'human_response': body['stimulus']['true_label'],
                'reaction_time_ms': 900,
                'self_confidence': 3,
                'reason_clicked': False,
                'evidence_opened': False,
                'verification_completed': False,
            },
        ).status_code == 200

    questionnaire = client.post(
        f'/api/v1/sessions/{session_id}/blocks/{block_id}/questionnaire',
        json={'burden': 20, 'trust': 30, 'usefulness': 40},
    )
    assert questionnaire.status_code == 200
    assert questionnaire.json()['saved_ack']['saved'] is True

    reloaded = TestClient(create_app(str(tmp_path / 'pilot_api.sqlite3')))
    progress = reloaded.get(f'/api/v1/sessions/{session_id}/progress').json()
    assert progress['last_activity_at'] is not None
    assert progress['current_stage'] in {'trial', 'questionnaire', 'awaiting_final_submit'}
