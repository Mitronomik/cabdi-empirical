import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';

import App from '../App';

function makeTrial(
  overrides: Record<string, unknown> = {},
  policyDecision: Record<string, unknown> = {},
) {
  return {
    block_id: 'practice',
    trial_id: 't_1',
    stimulus: {
      stimulus_id: 's_1',
      task_family: 'scam_not_scam',
      content_type: 'text',
      payload: {
        prompt: 'Test prompt',
        rationale: 'Because suspicious language',
        evidence: 'Evidence text',
        response_options: ['scam', 'not_scam'],
      },
      true_label: 'scam',
      difficulty_prior: 'low',
      model_prediction: 'scam',
      model_confidence: 'high',
      model_correct: true,
      eligible_sets: ['demo'],
    },
    policy_decision: {
      condition: 'cabdi_lite',
      risk_bucket: 'extreme',
      show_prediction: true,
      show_confidence: true,
      show_rationale: 'inline',
      show_evidence: true,
      verification_mode: 'forced_checkbox',
      compression_mode: 'none',
      max_extra_steps: 1,
      ui_help_level: 'high',
      ui_verification_level: 'high',
      budget_signature: {},
      ...policyDecision,
    },
    self_confidence_scale: { min: 0, max: 100, step: 1 },
    progress: { completed_trials: 0, total_trials: 12, current_ordinal: 1 },
    ...overrides,
  };
}

function mockFetchSequence(sequence: Array<{ status: number; body: unknown }>) {
  const fetchMock = vi.fn();
  sequence.forEach((item) => {
    fetchMock.mockResolvedValueOnce({
      ok: item.status >= 200 && item.status < 300,
      status: item.status,
      json: async () => item.body,
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.unstubAllGlobals();
  window.history.replaceState({}, '', '/');
  Object.defineProperty(window.navigator, 'language', {
    configurable: true,
    value: 'en-US',
  });
});

async function proceedToInstructionsAndStart(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByLabelText(/i consent to participate/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));
  await user.click(screen.getByRole('button', { name: /start study/i }));
}

test('participant entry no longer requires manual run slug input', async () => {
  window.history.replaceState({}, '', '/join/public-run-a');
  mockFetchSequence([
    { status: 200, body: { run_slug: 'public-run-a', public_title: 'Run A', launchable: true, run_status: 'active' } },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByLabelText(/i consent to participate/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));

  expect(screen.getByRole('heading', { name: /before you begin/i })).toBeInTheDocument();
  expect(screen.queryByLabelText(/run link slug/i)).not.toBeInTheDocument();
});

test('missing run context shows human-friendly onboarding message', async () => {
  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByLabelText(/i consent to participate/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));

  expect(screen.getByRole('heading', { name: /study link needed/i })).toBeInTheDocument();
});

test('language selector renders and switches onboarding copy', async () => {
  render(<App />);
  const user = userEvent.setup();

  expect(screen.getByLabelText(/language switcher/i)).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /consent/i })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'RU' }));
  expect(screen.getByRole('heading', { name: /согласие/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /продолжить/i })).toBeInTheDocument();
});

test('session creation sends selected participant language', async () => {
  window.history.replaceState({}, '', '/join/public-run-ru');
  const fetchMock = mockFetchSequence([
    { status: 200, body: { run_slug: 'public-run-ru', public_title: 'Run RU', launchable: true, run_status: 'active' } },
    { status: 200, body: { session_id: 'sess_1', resume_token: 'token_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 200, body: makeTrial() },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: 'RU' }));
  await user.click(screen.getByLabelText(/я согласен/i));
  await user.click(screen.getByRole('button', { name: /продолжить/i }));
  await user.click(screen.getByRole('button', { name: /начать исследование/i }));

  const createCall = fetchMock.mock.calls[1];
  expect(createCall[0]).toContain('/api/v1/sessions');
  expect(String((createCall[1] as RequestInit).body)).toContain('"language":"ru"');
  expect(String((createCall[1] as RequestInit).body)).toContain('"run_slug":"public-run-ru"');
});

test('trial screen progress uses backend truth', async () => {
  window.history.replaceState({}, '', '/join/public-run-a');
  mockFetchSequence([
    { status: 200, body: { run_slug: 'public-run-a', public_title: 'Run A', launchable: true, run_status: 'active' } },
    { status: 200, body: { session_id: 'sess_1', resume_token: 'token_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 200, body: makeTrial({ progress: { completed_trials: 4, total_trials: 12, current_ordinal: 5 } }) },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await proceedToInstructionsAndStart(user);

  await screen.findByTestId('trial-layout');
  expect(screen.getByText(/progress 5 \/ 12/i)).toBeInTheDocument();
  expect(screen.getByText(/ai suggestion/i)).toBeInTheDocument();
  expect(screen.getByText(/ai confidence/i)).toBeInTheDocument();
});

test('forced verification blocks submission until completed', async () => {
  window.history.replaceState({}, '', '/join/public-run-a');
  mockFetchSequence([
    { status: 200, body: { run_slug: 'public-run-a', public_title: 'Run A', launchable: true, run_status: 'active' } },
    { status: 200, body: { session_id: 'sess_1', resume_token: 'token_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 200, body: makeTrial() },
    { status: 200, body: { trial_id: 't_1', status: 'completed' } },
    { status: 200, body: { status: 'awaiting_final_submit', progress: { completed_trials: 12, total_trials: 12, current_ordinal: 12 } } },
    { status: 200, body: { session_id: 'sess_1', status: 'finalized', final_submit: 'accepted', already_finalized: false } },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await proceedToInstructionsAndStart(user);

  await screen.findByTestId('trial-layout');
  await user.click(screen.getAllByRole('button', { name: /^scam$/i })[0]);

  const submit = screen.getByRole('button', { name: /submit response/i });
  expect(submit).toBeDisabled();
  await user.click(screen.getByLabelText(/made my own decision/i));
  expect(submit).toBeEnabled();

  await user.click(submit);
  await screen.findByRole('heading', { name: /final confirmation required/i });
  await user.click(screen.getByRole('button', { name: /final submit/i }));
  await screen.findByRole('heading', { name: /study complete/i });
});

test('resume token is checked and reused for resume', async () => {
  window.history.replaceState({}, '', '/join/public-run-a');
  window.localStorage.setItem('participant_web.resume_token.public-run-a', 'resume-token-1');
  const fetchMock = mockFetchSequence([
    { status: 200, body: { run_slug: 'public-run-a', public_title: 'Run A', launchable: true, run_status: 'active' } },
    { status: 200, body: { resume_status: 'resumable', session_id: 'sess_1', session_status: 'in_progress' } },
    { status: 200, body: { resume_status: 'resumable', session_id: 'sess_1', session_status: 'in_progress', current_stage: 'trial' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress', current_stage: 'trial', current_block_index: 0, current_trial_index: 1 } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 200, body: makeTrial() },
  ]);

  render(<App />);
  const user = userEvent.setup();
  expect(await screen.findByText(/found your saved progress/i)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: /continue/i }));
  await screen.findByTestId('trial-layout');

  expect(fetchMock.mock.calls[1][0]).toContain('/api/v1/sessions/resume-info');
  expect(fetchMock.mock.calls[2][0]).toContain('/api/v1/sessions/resume');
  expect(String((fetchMock.mock.calls[2][1] as RequestInit).body)).toContain('"resume_token":"resume-token-1"');
});

test('invalid saved resume token is surfaced and session starts new', async () => {
  window.history.replaceState({}, '', '/join/public-run-a');
  window.localStorage.setItem('participant_web.resume_token.public-run-a', 'bad-token');
  const fetchMock = mockFetchSequence([
    { status: 200, body: { run_slug: 'public-run-a', public_title: 'Run A', launchable: true, run_status: 'active' } },
    { status: 200, body: { resume_status: 'invalid' } },
    { status: 200, body: { resume_status: 'invalid' } },
    { status: 200, body: { session_id: 'sess_2', resume_token: 'new-token', status: 'created', entry_mode: 'created' } },
    { status: 200, body: { session_id: 'sess_2', status: 'in_progress' } },
    { status: 200, body: makeTrial() },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByLabelText(/i consent to participate/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));
  expect(screen.getByText(/saved resume data was invalid/i)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: /start study/i }));
  await screen.findByTestId('trial-layout');

  expect(fetchMock.mock.calls[1][0]).toContain('/api/v1/sessions/resume-info');
  expect(fetchMock.mock.calls[2][0]).toContain('/api/v1/sessions/resume-info');
});

test('non-launchable run blocks start in participant flow', async () => {
  window.history.replaceState({}, '', '/join/public-run-paused');
  const fetchMock = mockFetchSequence([
    { status: 200, body: { run_slug: 'public-run-paused', public_title: 'Run paused', launchable: false, run_status: 'paused' } },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByLabelText(/i consent to participate/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));

  const startButton = screen.getByRole('button', { name: /start study/i });
  expect(startButton).toBeDisabled();
  expect(screen.getByText(/currently unavailable/i)).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test('questionnaire and completion flow remains operational', async () => {
  window.history.replaceState({}, '', '/join/public-run-a');
  const fetchMock = mockFetchSequence([
    { status: 200, body: { run_slug: 'public-run-a', public_title: 'Run A', launchable: true, run_status: 'active' } },
    { status: 200, body: { session_id: 'sess_1', resume_token: 'token_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 409, body: { detail: { message: 'block_questionnaire_required', block_id: 'block_1' } } },
    { status: 200, body: { block_id: 'block_1', status: 'submitted' } },
    { status: 200, body: { status: 'awaiting_final_submit', progress: { completed_trials: 12, total_trials: 12, current_ordinal: 12 } } },
    { status: 200, body: { session_id: 'sess_1', status: 'finalized', final_submit: 'accepted', already_finalized: false } },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await proceedToInstructionsAndStart(user);

  await screen.findByRole('heading', { name: /block questionnaire/i });
  expect(screen.getByText(/before continuing, please complete this short check-in/i)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: /continue/i }));
  await screen.findByRole('heading', { name: /final confirmation required/i });
  expect(screen.getByText(/saved but not fully completed/i)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: /final submit/i }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(7));
  await screen.findByRole('heading', { name: /study complete/i });
  expect(screen.getByText(/cannot be resumed/i)).toBeInTheDocument();
});
