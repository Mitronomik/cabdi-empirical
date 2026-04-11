import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import { messages } from '../i18n/messages';

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe('researcher run details refresh invariants', () => {
  it('keeps details interaction live across repeated details/refresh actions', async () => {
    const user = userEvent.setup();
    let runADetailCalls = 0;
    const detailsA = vi.fn(async () => {
      runADetailCalls += 1;
      const runName = runADetailCalls >= 2 ? 'run-a-v2' : 'run-a-v1';
      return new Response(JSON.stringify({ run_id: 'run_a', run_name: runName, run_status: 'draft', status: 'draft', launchability_state: 'not_launchable' }), { status: 200 });
    });

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'scam_detection', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(JSON.stringify([{ stimulus_set_id: 'stim_1', name: 'A', task_family: 'scam_detection', validation_status: 'valid', n_items: 3 }]), { status: 200 });
        }
        if (url.endsWith('/runs')) {
          return new Response(
            JSON.stringify([
              { run_id: 'run_a', run_name: 'run-a', public_slug: 'run-a', status: 'draft', task_family: 'scam_detection', linked_stimulus_set_ids: ['stim_1'], launchable: false, launchability_reason: 'draft' },
              { run_id: 'run_b', run_name: 'run-b', public_slug: 'run-b', status: 'paused', task_family: 'scam_detection', linked_stimulus_set_ids: ['stim_1'], launchable: true, launchability_reason: 'paused' },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/run_a')) return detailsA();
        if (url.endsWith('/runs/run_b')) {
          return new Response(JSON.stringify({ run_id: 'run_b', run_name: 'run-b-v1', run_status: 'paused', status: 'paused', launchability_state: 'launchable' }), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    const detailsHeading = await screen.findByText(messages.en['run.detailsTitle']);
    const detailsPanel = detailsHeading.closest('section');
    expect(detailsPanel).not.toBeNull();

    expect(await within(detailsPanel as HTMLElement).findByText(/Run name: run-a-v1/)).toBeInTheDocument();

    const detailsButtons = await screen.findAllByRole('button', { name: messages.en['run.detailsAction'] });
    await user.click(detailsButtons[1]);
    expect(await within(detailsPanel as HTMLElement).findByText(/Run name: run-b-v1/)).toBeInTheDocument();

    await user.click(detailsButtons[0]);
    expect(await within(detailsPanel as HTMLElement).findByText(/Run name: run-a-v2/)).toBeInTheDocument();
    expect(detailsA.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
