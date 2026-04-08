from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app
from app.researcher_api.main import create_app as create_researcher_app


def _login_researcher(client: TestClient) -> None:
    res = client.post('/admin/api/v1/auth/login', json={'username': 'admin', 'password': 'admin1234'})
    assert res.status_code == 200


def _make_client(tmp_path) -> TestClient:
    db_path = str(tmp_path / 'pilot_api.sqlite3')
    return TestClient(create_app(db_path))


def _bootstrap_run(tmp_path) -> str:
    db_path = str(tmp_path / 'pilot_api.sqlite3')
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
            'run_name': 'resume run',
            'experiment_id': 'toy_v1',
            'task_family': 'scam_detection',
            'config': {'mode': 'test', 'n_blocks': 1},
            'stimulus_set_ids': [upload.json()['stimulus_set_id']],
        },
    )
    assert researcher.post(f"/admin/api/v1/runs/{run.json()['run_id']}/activate").status_code == 200
    return run.json()['public_slug']


def test_refresh_restore_unfinished_session_and_stage(tmp_path) -> None:
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)

    created = client.post('/api/v1/sessions', json={'run_slug': run_slug}).json()
    session_id = created['session_id']
    resume_token = created['resume_token']

    assert client.post(f'/api/v1/sessions/{session_id}/start').status_code == 200
    next_trial = client.get(f'/api/v1/sessions/{session_id}/next-trial').json()
    submit = client.post(
        f"/api/v1/sessions/{session_id}/trials/{next_trial['trial_id']}/submit",
        json={
            'human_response': next_trial['stimulus']['true_label'],
            'reaction_time_ms': 900,
            'self_confidence': 3,
            'reason_clicked': False,
            'evidence_opened': False,
            'verification_completed': False,
        },
    )
    assert submit.status_code == 200

    resume_info = client.post('/api/v1/sessions/resume-info', json={'run_slug': run_slug, 'resume_token': resume_token})
    assert resume_info.status_code == 200
    assert resume_info.json()['resume_status'] == 'resumable'
    assert resume_info.json()['current_stage'] in {'practice', 'trial'}

    resumed = client.post('/api/v1/sessions/resume', json={'run_slug': run_slug, 'resume_token': resume_token})
    assert resumed.status_code == 200
    assert resumed.json()['session_id'] == session_id

    progress = client.get(f'/api/v1/sessions/{session_id}/progress')
    assert progress.status_code == 200
    assert progress.json()['current_stage'] in {'practice', 'trial'}
    assert progress.json()['current_block_index'] >= -1
    assert progress.json()['current_trial_index'] >= 0


def test_resumable_session_does_not_require_consent_again(tmp_path) -> None:
    client = _make_client(tmp_path)
    run_slug = _bootstrap_run(tmp_path)

    created = client.post('/api/v1/sessions', json={'run_slug': run_slug}).json()
    session_id = created['session_id']
    resume_token = created['resume_token']
    assert client.post(f'/api/v1/sessions/{session_id}/start').status_code == 200

    resumed = client.post('/api/v1/sessions/resume', json={'run_slug': run_slug, 'resume_token': resume_token})
    assert resumed.status_code == 200
    assert resumed.json()['resume_status'] == 'resumable'

    progress = client.get(f'/api/v1/sessions/{session_id}/progress').json()
    assert progress['consent_at'] is not None
    assert progress['current_stage'] != 'consent'
