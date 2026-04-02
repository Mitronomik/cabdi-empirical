import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

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

test('instructions screen renders', async () => {
  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByLabelText(/i consent/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));
  expect(screen.getByRole('heading', { name: /instructions/i })).toBeInTheDocument();
  expect(screen.getByText(/ai can be wrong/i)).toBeInTheDocument();
});

test('trial screen renders consistent layout and assistance panel', async () => {
  mockFetchSequence([
    { status: 200, body: { session_id: 'sess_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 200, body: makeTrial() },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByLabelText(/i consent/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));
  await user.click(screen.getByRole('button', { name: /start practice/i }));

  await screen.findByTestId('trial-layout');
  expect(screen.getByText(/trial 1 \/ 54/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/ai assistance panel/i)).toBeInTheDocument();
  expect(screen.getByText(/prediction:/i)).toBeInTheDocument();
});

test('forced verification blocks submission until completed', async () => {
  const fetchMock = mockFetchSequence([
    { status: 200, body: { session_id: 'sess_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 200, body: makeTrial() },
    { status: 200, body: { trial_id: 't_1', status: 'completed' } },
    { status: 200, body: { status: 'completed' } },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByLabelText(/i consent/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));
  await user.click(screen.getByRole('button', { name: /start practice/i }));

  await screen.findByTestId('trial-layout');
  await user.click(screen.getByRole('button', { name: 'scam' }));

  const submit = screen.getByRole('button', { name: /submit trial/i });
  expect(submit).toBeDisabled();
  await user.click(screen.getByLabelText(/independent judgment/i));
  expect(submit).toBeEnabled();

  await user.click(submit);
  await screen.findByRole('heading', { name: /complete/i });
  expect(fetchMock).toHaveBeenCalled();
});

test('rationale on-click mode works and evidence toggle works', async () => {
  mockFetchSequence([
    { status: 200, body: { session_id: 'sess_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    {
      status: 200,
      body: makeTrial({}, { show_rationale: 'on_click', show_evidence: true, verification_mode: 'none' }),
    },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByLabelText(/i consent/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));
  await user.click(screen.getByRole('button', { name: /start practice/i }));

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
    { status: 200, body: { session_id: 'sess_1' } },
    { status: 200, body: { session_id: 'sess_1', status: 'in_progress' } },
    { status: 409, body: { detail: { message: 'block_questionnaire_required', block_id: 'block_1' } } },
    { status: 200, body: { block_id: 'block_1', status: 'submitted' } },
    { status: 200, body: { status: 'completed' } },
  ]);

  render(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByLabelText(/i consent/i));
  await user.click(screen.getByRole('button', { name: /continue/i }));
  await user.click(screen.getByRole('button', { name: /start practice/i }));

  await screen.findByRole('heading', { name: /block questionnaire/i });
  await user.click(screen.getByRole('button', { name: /submit questionnaire/i }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
  await screen.findByRole('heading', { name: /complete/i });
});
