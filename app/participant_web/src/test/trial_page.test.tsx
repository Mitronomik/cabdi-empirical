import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test, vi } from 'vitest';

import { LocaleProvider } from '../i18n/useLocale';
import { TrialPage } from '../pages/TrialPage';
import type { TrialPayload } from '../lib/types';

function makeTrial(overrides: Partial<TrialPayload> = {}): TrialPayload {
  return {
    block_id: 'practice',
    trial_id: 't_1',
    stimulus: {
      stimulus_id: 's_1',
      task_family: 'scam_not_scam',
      content_type: 'text',
      payload: {
        title: 'Case',
        body: 'Body',
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
      verification_mode: 'none',
      compression_mode: 'none',
      max_extra_steps: 1,
      ui_help_level: 'high',
      ui_verification_level: 'high',
      budget_signature: {},
    },
    self_confidence_scale: { type: '4_point', min: 1, max: 4, step: 1 },
    progress: { completed_trials: 0, total_trials: 12, current_ordinal: 1 },
    ...overrides,
  };
}

function renderTrial(trial: TrialPayload, onSubmit = vi.fn()) {
  render(
    <LocaleProvider>
      <TrialPage trial={trial} loading={false} onSubmit={onSubmit} />
    </LocaleProvider>,
  );
}

afterEach(() => {
  cleanup();
});

test('trial page prefers payload response_options over legacy defaults', () => {
  const trial = makeTrial({
    stimulus: {
      ...makeTrial().stimulus,
      payload: {
        title: 'Case',
        body: 'Body',
        response_options: ['allow', 'block'],
      },
    },
  });
  renderTrial(trial);

  expect(screen.getByRole('radio', { name: 'allow' })).toBeInTheDocument();
  expect(screen.getByRole('radio', { name: 'block' })).toBeInTheDocument();
  expect(screen.queryByRole('radio', { name: /scam/i })).not.toBeInTheDocument();
});

test('trial page supports payload response_options with explicit labels', () => {
  const trial = makeTrial({
    stimulus: {
      ...makeTrial().stimulus,
      payload: {
        title: 'Case',
        body: 'Body',
        response_options: [
          { value: 'allow', label: 'Allow transfer' },
          { value: 'block', label: 'Block transfer' },
        ],
      },
    },
  });
  renderTrial(trial);

  expect(screen.getByRole('radio', { name: 'Allow transfer' })).toBeInTheDocument();
  expect(screen.getByRole('radio', { name: 'Block transfer' })).toBeInTheDocument();
});

test('trial page keeps family defaults when response_options are absent', () => {
  const trial = makeTrial();
  renderTrial(trial);

  expect(screen.getByRole('radio', { name: 'Scam' })).toBeInTheDocument();
  expect(screen.getByRole('radio', { name: 'Not a scam' })).toBeInTheDocument();
});

test('trial page shows explicit error when no payload or fallback response options exist', () => {
  const trial = makeTrial({
    stimulus: {
      ...makeTrial().stimulus,
      task_family: 'custom_runtime_family',
      payload: {
        title: 'Case',
        body: 'Body',
      },
    },
  });
  renderTrial(trial);

  expect(screen.getByRole('alert')).toHaveTextContent('Unable to render response options for this trial');
  expect(screen.queryByRole('radio', { name: 'Scam' })).not.toBeInTheDocument();
});

test('confidence UI no longer shows obsolete low/high slider labels', async () => {
  const trial = makeTrial();
  renderTrial(trial);

  const user = userEvent.setup();
  await user.click(screen.getByRole('radio', { name: 'Scam' }));

  expect(screen.queryByText(/low confidence/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/high confidence/i)).not.toBeInTheDocument();
  expect(screen.getByText(/not confident at all/i)).toBeInTheDocument();
  expect(screen.getByText(/very confident/i)).toBeInTheDocument();
});

test('forced second look must be completed before submit is enabled', async () => {
  const onSubmit = vi.fn();
  const trial = makeTrial({
    policy_decision: {
      ...makeTrial().policy_decision,
      verification_mode: 'forced_second_look',
    },
  });
  renderTrial(trial, onSubmit);

  const user = userEvent.setup();
  await user.click(screen.getByRole('radio', { name: 'Scam' }));
  await user.click(screen.getByLabelText(/very confident/i));

  const submit = screen.getByRole('button', { name: /submit response/i });
  expect(submit).toBeDisabled();

  await user.click(screen.getByRole('button', { name: /i completed a second look/i }));
  expect(submit).toBeEnabled();

  await user.click(submit);
  expect(onSubmit).toHaveBeenCalledTimes(1);
});
