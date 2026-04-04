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
  Object.defineProperty(window.navigator, 'language', {
    configurable: true,
    value: 'en-US',
  });
});


async function proceedToInstructionsAndStart(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByLabelText(/i consent to participate/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));
  await user.type(screen.getByLabelText(/run link slug/i), 'public-run-a');
  await user.click(screen.getByRole('button', { name: /start practice/i }));
}

test('instructions screen renders', async () => {
  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByLabelText(/i consent to participate/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));
  expect(screen.getByRole('heading', { name: /instructions/i })).toBeInTheDocument();
  expect(screen.getByText(/ai can be wrong/i)).toBeInTheDocument();
});

test('language selector renders and switches onboarding copy', async () => {
  render(<App />);
  const user = userEvent.setup();

  expect(screen.getByLabelText(/language switcher/i)).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /consent/i })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'RU' }));
  expect(screen.getByRole('heading', { name: /согласие/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /продолжить/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/переключатель языка/i)).toBeInTheDocument();
});

test('default language follows browser locale on first load', () => {
  Object.defineProperty(window.navigator, 'language', {
    configurable: true,
    value: 'ru-RU',
  });

  render(<App />);
  expect(screen.getByRole('heading', { name: /согласие/i })).toBeInTheDocument();
});

test('saved language in localStorage overrides browser locale', () => {
  window.localStorage.setItem('participant_web.locale', 'en');
  Object.defineProperty(window.navigator, 'language', {
    configurable: true,
    value: 'ru-RU',
  });

  render(<App />);
  expect(screen.getByRole('heading', { name: /consent/i })).toBeInTheDocument();
});

test('selected language persists across remount', async () => {
  const user = userEvent.setup();
  const { unmount } = render(<App />);

  await user.click(screen.getByRole('button', { name: 'RU' }));
  expect(screen.getByRole('heading', { name: /согласие/i })).toBeInTheDocument();

  unmount();
  render(<App />);
  expect(screen.getByRole('heading', { name: /согласие/i })).toBeInTheDocument();
});



test('session creation sends selected participant language', async () => {
  const fetchMock = mockFetchSequence([
    {
      status: 200,
      body: {
        run_slug: 'public-run-ru',
        public_title: 'Run RU',
        launchable: true,
        run_status: 'active',
      },
    },
    { status: 200, body: { session_id: 'sess_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 200, body: makeTrial() },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: 'RU' }));
  await user.click(screen.getByLabelText(/я согласен/i));
  await user.click(screen.getByRole('button', { name: /продолжить/i }));
  await user.type(screen.getByLabelText(/публичный slug запуска/i), 'public-run-ru');
  await user.click(screen.getByRole('button', { name: /начать тренировку/i }));

  expect(fetchMock).toHaveBeenCalled();
  const createCall = fetchMock.mock.calls[1];
  expect(createCall[0]).toContain('/api/v1/sessions');
  expect(String((createCall[1] as RequestInit).body)).toContain('"language":"ru"');
  expect(String((createCall[1] as RequestInit).body)).toContain('"run_slug":"public-run-ru"');
  expect(String((createCall[1] as RequestInit).body)).not.toContain('experiment_id');
});
test('trial screen renders consistent layout and assistance panel', async () => {
  mockFetchSequence([
    {
      status: 200,
      body: { run_slug: 'public-run-a', public_title: 'Run A', launchable: true, run_status: 'active' },
    },
    { status: 200, body: { session_id: 'sess_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 200, body: makeTrial() },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await proceedToInstructionsAndStart(user);

  await screen.findByTestId('trial-layout');
  expect(screen.getByText(/trial 1 \/ [0-9]+/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/ai assistance panel/i)).toBeInTheDocument();
  expect(screen.getByText(/prediction:/i)).toBeInTheDocument();
});

test('forced verification blocks submission until completed', async () => {
  const fetchMock = mockFetchSequence([
    {
      status: 200,
      body: { run_slug: 'public-run-a', public_title: 'Run A', launchable: true, run_status: 'active' },
    },
    { status: 200, body: { session_id: 'sess_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 200, body: makeTrial() },
    { status: 200, body: { trial_id: 't_1', status: 'completed' } },
    { status: 200, body: { status: 'awaiting_final_submit' } },
    { status: 200, body: { session_id: 'sess_1', status: 'finalized', final_submit: 'accepted', already_finalized: false } },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await proceedToInstructionsAndStart(user);

  await screen.findByTestId('trial-layout');
  await user.click(screen.getByRole('button', { name: 'scam' }));

  const submit = screen.getByRole('button', { name: /submit trial/i });
  expect(submit).toBeDisabled();
  await user.click(screen.getByLabelText(/independent judgment/i));
  expect(submit).toBeEnabled();

  await user.click(submit);
  await screen.findByRole('heading', { name: /final submit required/i });
  await user.click(screen.getByRole('button', { name: /final submit/i }));
  await screen.findByRole('heading', { name: /complete/i });
  expect(fetchMock).toHaveBeenCalled();
});

test('rationale on-click mode works and evidence toggle works', async () => {
  mockFetchSequence([
    {
      status: 200,
      body: { run_slug: 'public-run-a', public_title: 'Run A', launchable: true, run_status: 'active' },
    },
    { status: 200, body: { session_id: 'sess_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    {
      status: 200,
      body: makeTrial({}, { show_rationale: 'on_click', show_evidence: true, verification_mode: 'none' }),
    },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await proceedToInstructionsAndStart(user);

  await screen.findByTestId('trial-layout');
  expect(screen.queryByTestId('rationale-on-click')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: /show rationale/i }));
  expect(screen.getByTestId('rationale-on-click')).toBeInTheDocument();

  expect(screen.queryByTestId('evidence-content')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: /show evidence/i }));
  expect(screen.getByTestId('evidence-content')).toBeInTheDocument();
});

test('block-end questionnaire submits and completion flow appears', async () => {
  const fetchMock = mockFetchSequence([
    {
      status: 200,
      body: { run_slug: 'public-run-a', public_title: 'Run A', launchable: true, run_status: 'active' },
    },
    { status: 200, body: { session_id: 'sess_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 409, body: { detail: { message: 'block_questionnaire_required', block_id: 'block_1' } } },
    { status: 200, body: { block_id: 'block_1', status: 'submitted' } },
    { status: 200, body: { status: 'awaiting_final_submit' } },
    { status: 200, body: { session_id: 'sess_1', status: 'finalized', final_submit: 'accepted', already_finalized: false } },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await proceedToInstructionsAndStart(user);

  await screen.findByRole('heading', { name: /block questionnaire/i });
  await user.click(screen.getByRole('button', { name: /submit questionnaire/i }));

  await screen.findByRole('heading', { name: /final submit required/i });
  await user.click(screen.getByRole('button', { name: /final submit/i }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(7));
  await screen.findByRole('heading', { name: /complete/i });
});

test('saved resume token is checked server-side and reused for session resume', async () => {
  window.localStorage.setItem('participant_web.resume_token.public-run-a', 'resume-token-1');
  const fetchMock = mockFetchSequence([
    {
      status: 200,
      body: { run_slug: 'public-run-a', public_title: 'Run A', launchable: true, run_status: 'active' },
    },
    { status: 200, body: { resume_status: 'resumable', session_id: 'sess_1', session_status: 'in_progress' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress', entry_mode: 'resumed', resume_token: 'resume-token-1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 200, body: makeTrial() },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await proceedToInstructionsAndStart(user);
  await screen.findByTestId('trial-layout');

  expect(fetchMock.mock.calls[1][0]).toContain('/api/v1/sessions/resume-info');
  expect(String((fetchMock.mock.calls[2][1] as RequestInit).body)).toContain('"resume_token":"resume-token-1"');
  expect(window.localStorage.getItem('participant_web.resume_token.public-run-a')).toBe('resume-token-1');
});
