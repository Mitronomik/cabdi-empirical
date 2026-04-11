import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import { messages } from '../i18n/messages';

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe('researcher auth shell', () => {
  it('shows login form when unauthenticated', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'unauthorized' }), { status: 401 })));

    render(<App />);

    expect(await screen.findByText('Researcher Login')).toBeInTheDocument();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('shows infrastructure error state when auth check has transport failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch')));

    render(<App />);

    expect(await screen.findByText('Researcher service unavailable')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Researcher service is unavailable.');
    expect(screen.queryByText('Researcher Login')).not.toBeInTheDocument();
  });

  it('shows infrastructure error state when auth check returns backend failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'backend unavailable' }), { status: 503 })));

    render(<App />);

    expect(await screen.findByText('Researcher service unavailable')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('backend unavailable');
    expect(screen.queryByText('Researcher Login')).not.toBeInTheDocument();
  });

  it('supports login success and shows cabinet', async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'unauthorized' }), { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 }),
      )
      .mockImplementation(async () => new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await user.type(await screen.findByLabelText('Username'), 'admin');
    await user.type(screen.getByLabelText('Password'), 'admin1234');
    await user.click(screen.getByRole('button', { name: 'Login' }));

    expect(await screen.findByText('Logged in as: admin')).toBeInTheDocument();
    expect(screen.getByRole('navigation')).toBeInTheDocument();
    expect(screen.getByText('Pilot workflow')).toBeInTheDocument();
  });

  it('handles login failure and keeps cabinet inaccessible', async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'unauthorized' }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Invalid username or password' }), { status: 401 }));
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await user.type(await screen.findByLabelText('Username'), 'admin');
    await user.type(screen.getByLabelText('Password'), 'wrong');
    await user.click(screen.getByRole('button', { name: 'Login' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password.');
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('supports logout and clears access', async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }))
      .mockImplementation(async () => new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    expect(await screen.findByText('Logged in as: admin')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Logout' }));

    await waitFor(() => expect(screen.getByText('Researcher Login')).toBeInTheDocument());
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('uses readable run selector labels in monitor flow', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs')) {
          return new Response(
            JSON.stringify([
              {
                run_id: 'run_1',
                run_name: 'pilot-run',
                public_slug: 'pilot-run',
                status: 'active',
                task_family: 'scam_detection',
                linked_stimulus_set_ids: ['stim_1'],
                launchable: true,
                launchability_reason: 'run is active and accepts participant sessions',
              },
            ]),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 3: Monitor Sessions' }));

    expect(await screen.findByText(/Selected run: pilot-run • \/pilot-run • Active/)).toBeInTheDocument();
    expect(screen.getByText('run_1')).toBeInTheDocument();
  });

  it('switches language and persists researcher locale', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'unauthorized' }), { status: 401 })));

    const { unmount } = render(<App />);
    await user.click(screen.getByRole('button', { name: 'RU' }));
    expect(await screen.findByText('Вход исследователя')).toBeInTheDocument();
    expect(window.localStorage.getItem('researcher_web.locale')).toBe('ru');

    unmount();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'unauthorized' }), { status: 401 })));
    render(<App />);
    expect(await screen.findByText('Вход исследователя')).toBeInTheDocument();
  });

  it('localizes operator statuses in run/session surfaces', async () => {
    const user = userEvent.setup();
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
          return new Response(JSON.stringify([{ stimulus_set_id: 'stim_1', name: 'A', task_family: 'scam_detection', validation_status: 'warning_only', n_items: 3 }]), { status: 200 });
        }
        if (url.endsWith('/runs')) {
          return new Response(JSON.stringify([{ run_id: 'run_1', run_name: 'pilot-run', public_slug: 'pilot-run', status: 'active', task_family: 'scam_detection', linked_stimulus_set_ids: ['stim_1'], launchable: true, launchability_reason: 'ok' }]), { status: 200 });
        }
        if (url.endsWith('/runs/run_1/sessions')) {
          return new Response(JSON.stringify({ run_status: 'paused', sessions: [], counts: {} }), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'RU' }));
    await user.click(screen.getByRole('button', { name: 'Шаг 3: Мониторинг сессий' }));
    await user.click(await screen.findByRole('button', { name: 'Загрузить сессии' }));

    expect(await screen.findByText(/Выбранный запуск: pilot-run • \/pilot-run • Активен/)).toBeInTheDocument();
    expect(await screen.findByText('Сводка сессий')).toBeInTheDocument();
    expect(screen.getByText('На паузе')).toBeInTheDocument();
  });

  it('confirms lifecycle action before close', async () => {
    const user = userEvent.setup();
    const confirmMock = vi.fn().mockReturnValue(false);
    vi.stubGlobal('confirm', confirmMock);

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(JSON.stringify([{ stimulus_set_id: 'stim_1', name: 'A', task_family: 'scam_detection', validation_status: 'valid', n_items: 3 }]), {
            status: 200,
          });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'scam_detection', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/runs')) {
          return new Response(
            JSON.stringify([
              {
                run_id: 'run_1',
                run_name: 'pilot-run',
                public_slug: 'pilot-run',
                status: 'active',
                task_family: 'scam_detection',
                linked_stimulus_set_ids: ['stim_1'],
                launchable: true,
                launchability_reason: 'run is active and accepts participant sessions',
              },
            ]),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.click(await screen.findByRole('button', { name: 'Close' }));

    expect(confirmMock).toHaveBeenCalled();
  });
  it('shows session summary cards and localized status badges after loading sessions', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs')) {
          return new Response(
            JSON.stringify([
              { run_id: 'run_1', run_name: 'pilot-run', public_slug: 'pilot-run', status: 'active', task_family: 'scam_detection', linked_stimulus_set_ids: ['stim_1'], launchable: true, launchability_reason: 'ok' },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/run_1/sessions')) {
          return new Response(
            JSON.stringify({
              run_status: 'active',
              counts: { in_progress: 1, completed: 1 },
              sessions: [
                {
                  session_id: 's_1',
                  participant_id: 'p_1',
                  status: 'in_progress',
                  current_block_index: 1,
                  current_trial_index: 2,
                  started_at: '2026-01-01T00:00:00Z',
                  last_activity_at: '2026-01-01T00:10:00Z',
                  completed_at: null,
                },
              ],
            }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 3: Monitor Sessions' }));
    await user.click(await screen.findByRole('button', { name: 'Load Sessions' }));

    expect(await screen.findByText('Session snapshot')).toBeInTheDocument();
    expect(screen.getByText('In progress: 1')).toBeInTheDocument();
    expect(screen.getByText('Session details')).toBeInTheDocument();
  });

  it('renders backend-derived run counts in run details without defaulting to 54', async () => {
    const user = userEvent.setup();
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
          return new Response(JSON.stringify([{ stimulus_set_id: 'stim_1', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 6 }]), {
            status: 200,
          });
        }
        if (url.endsWith('/runs/run_1')) {
          return new Response(
            JSON.stringify({
              run_id: 'run_1',
              run_name: 'pilot-run',
              public_slug: 'pilot-run',
              status: 'draft',
              run_status: 'draft',
              task_family: 'scam_detection',
              linked_stimulus_set_ids: ['stim_1'],
              launchable: false,
              launchability_state: 'not_launchable',
              launchability_reason: 'draft',
              run_summary: {
                banks: [{ stimulus_set_id: 'stim_1', name: 'Main A', n_items: 6, role: 'main' }],
                practice_item_count: 0,
                total_main_items: 6,
                expected_trial_count: 6,
              },
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/preview')) {
          return new Response(
            JSON.stringify({
              resolved_task_family: 'scam_detection',
              validation_errors: [],
              operator_warnings: [],
              practice_item_count: 0,
              main_item_count: 6,
              expected_trial_count: 6,
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs')) {
          return new Response(
            JSON.stringify([
              {
                run_id: 'run_1',
                run_name: 'pilot-run',
                public_slug: 'pilot-run',
                status: 'draft',
                task_family: 'scam_detection',
                linked_stimulus_set_ids: ['stim_1'],
                aggregation_mode: 'single',
                launchable: false,
                launchability_reason: 'draft',
              },
            ]),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    expect((await screen.findAllByText('Total main items: 6')).length).toBeGreaterThanOrEqual(1);
    expect((await screen.findAllByText('Expected trial count: 6')).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText('Expected trial count: 54')).not.toBeInTheDocument();
  });

  it('keeps pre-activation summary bound to current draft form when selected run details have larger counts', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'scam_detection', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_main', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 6 },
              { stimulus_set_id: 'stim_other', name: 'Main B', task_family: 'scam_detection', validation_status: 'valid', n_items: 48 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs') && (!init?.method || init.method === 'GET')) {
          return new Response(
            JSON.stringify([
              {
                run_id: 'run_1',
                run_name: 'pilot-run',
                public_slug: 'pilot-run',
                status: 'draft',
                task_family: 'scam_detection',
                linked_stimulus_set_ids: ['stim_main'],
                aggregation_mode: 'single',
                launchable: false,
                launchability_reason: 'draft',
              },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/run_1')) {
          return new Response(
            JSON.stringify({
              run_id: 'run_1',
              run_name: 'pilot-run',
              public_slug: 'pilot-run',
              status: 'draft',
              run_status: 'draft',
              task_family: 'scam_detection',
              linked_stimulus_set_ids: ['stim_main'],
              launchable: false,
              launchability_state: 'not_launchable',
              launchability_reason: 'draft',
              run_summary: {
                practice_item_count: 6,
                main_item_count: 48,
                expected_trial_count: 54,
              },
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/preview')) {
          return new Response(
            JSON.stringify({
              resolved_task_family: 'scam_detection',
              validation_errors: [],
              operator_warnings: [],
              practice_item_count: 0,
              main_item_count: 6,
              expected_trial_count: 6,
            }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    const draftSummarySection = (await screen.findByText('Run summary before activation')).closest('section');
    expect(draftSummarySection).not.toBeNull();
    expect(within(draftSummarySection as HTMLElement).getByText('Total practice items: 0')).toBeInTheDocument();
    expect(within(draftSummarySection as HTMLElement).getByText('Total main items: 6')).toBeInTheDocument();
    expect(within(draftSummarySection as HTMLElement).getByText('Expected trial count: 6')).toBeInTheDocument();
    expect(within(draftSummarySection as HTMLElement).queryByText('Expected trial count: 54')).not.toBeInTheDocument();
  });

  it('computes pre-activation summary from draft selection practice + main independent of selected run details', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'scam_detection', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_main', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 48 },
              { stimulus_set_id: 'stim_practice', name: 'Practice A', task_family: 'scam_detection', validation_status: 'valid', n_items: 6 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs') && (!init?.method || init.method === 'GET')) {
          return new Response(
            JSON.stringify([
              {
                run_id: 'run_1',
                run_name: 'pilot-run',
                public_slug: 'pilot-run',
                status: 'draft',
                task_family: 'scam_detection',
                linked_stimulus_set_ids: ['stim_main'],
                aggregation_mode: 'single',
                launchable: false,
                launchability_reason: 'draft',
              },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/run_1')) {
          return new Response(
            JSON.stringify({
              run_id: 'run_1',
              run_name: 'pilot-run',
              public_slug: 'pilot-run',
              status: 'draft',
              run_status: 'draft',
              task_family: 'scam_detection',
              linked_stimulus_set_ids: ['stim_main'],
              launchable: false,
              launchability_state: 'not_launchable',
              launchability_reason: 'draft',
              run_summary: {
                practice_item_count: 1,
                main_item_count: 2,
                expected_trial_count: 3,
              },
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/preview')) {
          return new Response(
            JSON.stringify({
              resolved_task_family: 'scam_detection',
              validation_errors: [],
              operator_warnings: [],
              practice_item_count: 6,
              main_item_count: 48,
              expected_trial_count: 54,
            }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.selectOptions(screen.getByDisplayValue('Practice bank (optional supplementary)'), 'stim_practice');

    const draftSummarySection = (await screen.findByText(messages.en['run.preActivationSummaryTitle'])).closest('section');
    expect(draftSummarySection).not.toBeNull();
    expect(within(draftSummarySection as HTMLElement).getByText(`${messages.en['run.totalPracticeItems']}: 6`)).toBeInTheDocument();
    expect(within(draftSummarySection as HTMLElement).getByText(`${messages.en['run.totalMainItems']}: 48`)).toBeInTheDocument();
    expect(within(draftSummarySection as HTMLElement).getByText(`${messages.en['run.expectedTrialCount']}: 54`)).toBeInTheDocument();
  });

  it('loads details when clicking Details on a non-selected run', async () => {
    const user = userEvent.setup();
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
              { run_id: 'run_1', run_name: 'run-1', public_slug: 'run-1', status: 'draft', task_family: 'scam_detection', linked_stimulus_set_ids: ['stim_1'], launchable: false, launchability_reason: 'draft' },
              { run_id: 'run_2', run_name: 'run-2', public_slug: 'run-2', status: 'paused', task_family: 'scam_detection', linked_stimulus_set_ids: ['stim_1'], launchable: true, launchability_reason: 'paused' },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/run_1')) {
          return new Response(JSON.stringify({ run_id: 'run_1', run_name: 'run-1', run_status: 'draft', status: 'draft', launchability_state: 'not_launchable' }), { status: 200 });
        }
        if (url.endsWith('/runs/run_2')) {
          return new Response(JSON.stringify({ run_id: 'run_2', run_name: 'run-2', run_status: 'paused', status: 'paused', launchability_state: 'launchable' }), { status: 200 });
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
    expect(within(detailsPanel as HTMLElement).getByText(/Run name: run-1/)).toBeInTheDocument();
    await user.click((await screen.findAllByRole('button', { name: messages.en['run.detailsAction'] }))[1]);
    expect(await within(detailsPanel as HTMLElement).findByText(/Run name: run-2/)).toBeInTheDocument();
  });

  it('refreshes details when clicking Details on the already-selected run', async () => {
    const user = userEvent.setup();
    const run1DetailsFetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: 'run_1', run_name: 'run-1-a', run_status: 'draft', status: 'draft', launchability_state: 'not_launchable' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: 'run_1', run_name: 'run-1-b', run_status: 'draft', status: 'draft', launchability_state: 'not_launchable' }), { status: 200 }));
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
            JSON.stringify([{ run_id: 'run_1', run_name: 'run-1', public_slug: 'run-1', status: 'draft', task_family: 'scam_detection', linked_stimulus_set_ids: ['stim_1'], launchable: false, launchability_reason: 'draft' }]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/run_1')) {
          return run1DetailsFetch();
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    expect(await screen.findByText(/Run name: run-1-a/)).toBeInTheDocument();
    await user.click(await screen.findByRole('button', { name: messages.en['run.detailsAction'] }));
    expect(await screen.findByText(/Run name: run-1-b/)).toBeInTheDocument();
    expect(run1DetailsFetch).toHaveBeenCalledTimes(2);
  });

  it('keeps copy link action available when invite_url exists', async () => {
    const user = userEvent.setup();
    const clipboardWrite = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window.navigator, 'clipboard', {
      value: { writeText: clipboardWrite },
      configurable: true,
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
            JSON.stringify([{ run_id: 'run_1', run_name: 'run-1', public_slug: 'run-1', status: 'draft', task_family: 'scam_detection', linked_stimulus_set_ids: ['stim_1'], launchable: false, launchability_reason: 'draft' }]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/run_1')) {
          return new Response(
            JSON.stringify({ run_id: 'run_1', run_name: 'run-1', run_status: 'draft', status: 'draft', launchability_state: 'not_launchable', invite_url: 'https://cabdi.local/r/run-1' }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    const copyButton = await screen.findByRole('button', { name: messages.en['run.copyLink'] });
    expect(copyButton).toBeEnabled();
    await user.click(copyButton);
    expect(clipboardWrite).toHaveBeenCalledWith('https://cabdi.local/r/run-1');
    expect(await screen.findByText(messages.en['run.participantLinkCopied'])).toBeInTheDocument();
  });

  it('excludes selected main bank from practice selector options', async () => {
    const user = userEvent.setup();
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
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_main', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 48 },
              { stimulus_set_id: 'stim_practice', name: 'Practice A', task_family: 'scam_detection', validation_status: 'valid', n_items: 6 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    const practiceSelect = screen.getByDisplayValue('Practice bank (optional supplementary)');
    expect(within(practiceSelect).queryByRole('option', { name: /Main A/ })).not.toBeInTheDocument();
    expect(within(practiceSelect).getByRole('option', { name: /Practice A/ })).toBeInTheDocument();
  });

  it('excludes selected practice bank from main selector options in single and multi selection', async () => {
    const user = userEvent.setup();
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
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_main', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 48 },
              { stimulus_set_id: 'stim_other', name: 'Main B', task_family: 'scam_detection', validation_status: 'valid', n_items: 40 },
              { stimulus_set_id: 'stim_practice', name: 'Practice A', task_family: 'scam_detection', validation_status: 'valid', n_items: 6 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.selectOptions(screen.getByDisplayValue('Practice bank (optional supplementary)'), 'stim_practice');

    expect(screen.queryByRole('option', { name: /Practice A • scam_detection • 6 • Valid/ })).not.toBeInTheDocument();

    await user.click(screen.getByLabelText('Aggregation mode'));
    const multiSelect = screen.getByLabelText('Main banks');
    expect(within(multiSelect).queryByRole('option', { name: /Practice A/ })).not.toBeInTheDocument();
    expect(within(multiSelect).getByRole('option', { name: /Main A/ })).toBeInTheDocument();
  });

  it('single mode derives task family and payload from the selected main bank', async () => {
    const user = userEvent.setup();
    const createPayloadRef: { value: Record<string, unknown> | null } = { value: null };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'default_family', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_scam', name: 'Main Scam', task_family: 'scam_detection', validation_status: 'valid', n_items: 10 },
              { stimulus_set_id: 'stim_claim', name: 'Main Claim', task_family: 'claim_review', validation_status: 'valid', n_items: 8 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs') && init?.method === 'POST') {
          createPayloadRef.value = JSON.parse(String(init.body ?? '{}')) as Record<string, unknown>;
          return new Response(JSON.stringify({ run_id: 'run_new', run_name: 'run-new', public_slug: 'run-new', status: 'draft' }), { status: 200 });
        }
        if (url.endsWith('/runs/preview')) {
          return new Response(
            JSON.stringify({
              resolved_task_family: 'claim_review',
              validation_errors: [],
              operator_warnings: [],
              practice_item_count: 0,
              main_item_count: 8,
              expected_trial_count: 8,
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        if (url.endsWith('/runs/run_new')) return new Response(JSON.stringify({ run_id: 'run_new', run_name: 'run-new', status: 'draft' }), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    await user.selectOptions(screen.getByDisplayValue('Main Scam • scam_detection • 10 • Valid'), 'stim_claim');
    expect(screen.getByLabelText('task family')).toHaveValue('claim_review');
    expect(screen.getByText(/Selected stimulus set: Main Claim/)).toBeInTheDocument();
    expect(screen.getByText('Main bank(s): Main Claim (8)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create Run' }));

    await waitFor(() => expect(createPayloadRef.value).not.toBeNull());
    if (!createPayloadRef.value) {
      throw new Error('Expected create payload to be captured');
    }
    const payload = createPayloadRef.value;
    expect(payload.stimulus_set_ids).toEqual(['stim_claim']);
    expect(payload.task_family).toBe('claim_review');
  });

  it('uses backend preview selection summary for main-bank label instead of local stimulus metadata', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'default_family', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([{ stimulus_set_id: 'stim_claim', name: 'Stale Local Name', task_family: 'claim_review', validation_status: 'valid', n_items: 8 }]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/preview')) {
          return new Response(
            JSON.stringify({
              resolved_task_family: 'claim_review',
              validation_errors: [],
              operator_warnings: [],
              practice_item_count: 0,
              main_item_count: 8,
              expected_trial_count: 8,
              selection_summary: {
                task_family_field_state: 'resolved',
                task_family_field_value: 'claim_review',
                main_bank_summary_label: 'Canonical Backend Name (8)',
                main_banks: [{ stimulus_set_id: 'stim_claim', name: 'Canonical Backend Name', n_items: 8, validation_status: 'valid' }],
              },
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    expect(await screen.findByText('Main bank(s): Canonical Backend Name (8)')).toBeInTheDocument();
    expect(screen.queryByText('Main bank(s): Stale Local Name (8)')).not.toBeInTheDocument();
  });

  it('multi mode derives task family and payload from selected banks only when consistent', async () => {
    const user = userEvent.setup();
    const createPayloadRef: { value: Record<string, unknown> | null } = { value: null };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'default_family', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_single', name: 'Single Main', task_family: 'scam_detection', validation_status: 'valid', n_items: 10 },
              { stimulus_set_id: 'stim_multi_a', name: 'Multi A', task_family: 'claim_review', validation_status: 'valid', n_items: 8 },
              { stimulus_set_id: 'stim_multi_b', name: 'Multi B', task_family: 'claim_review', validation_status: 'valid', n_items: 7 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs') && init?.method === 'POST') {
          createPayloadRef.value = JSON.parse(String(init.body ?? '{}')) as Record<string, unknown>;
          return new Response(JSON.stringify({ run_id: 'run_new', run_name: 'run-new', public_slug: 'run-new', status: 'draft' }), { status: 200 });
        }
        if (url.endsWith('/runs/preview')) {
          return new Response(
            JSON.stringify({
              resolved_task_family: 'claim_review',
              validation_errors: [],
              operator_warnings: [],
              practice_item_count: 0,
              main_item_count: 15,
              expected_trial_count: 15,
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        if (url.endsWith('/runs/run_new')) return new Response(JSON.stringify({ run_id: 'run_new', run_name: 'run-new', status: 'draft' }), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.click(screen.getByLabelText('Aggregation mode'));
    const multiSelect = screen.getByLabelText('Main banks');
    await user.deselectOptions(multiSelect, ['stim_single']);
    await user.selectOptions(multiSelect, ['stim_multi_a', 'stim_multi_b']);

    expect(screen.getByLabelText('task family')).toHaveValue('claim_review');
    expect(screen.queryByText(/Selected stimulus set:/)).not.toBeInTheDocument();
    expect(screen.getByText('Main bank(s): Multi A (8), Multi B (7)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create Run' }));

    await waitFor(() => expect(createPayloadRef.value).not.toBeNull());
    if (!createPayloadRef.value) {
      throw new Error('Expected create payload to be captured');
    }
    const payload = createPayloadRef.value;
    expect(payload.stimulus_set_ids).toEqual(['stim_multi_a', 'stim_multi_b']);
    expect(payload.task_family).toBe('claim_review');
  });

  it('blocks submit in multi mode when selected banks have mixed task families', async () => {
    const user = userEvent.setup();
    const createSpy = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'default_family', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_a', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 10 },
              { stimulus_set_id: 'stim_b', name: 'Main B', task_family: 'claim_review', validation_status: 'valid', n_items: 8 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs') && init?.method === 'POST') {
          createSpy();
          return new Response(JSON.stringify({ run_id: 'run_new' }), { status: 200 });
        }
        if (url.endsWith('/runs/preview')) {
          return new Response(
            JSON.stringify({
              resolved_task_family: '',
              validation_errors: ['Selected main banks have mixed task families. Choose banks with one shared task family.'],
              operator_warnings: [],
              practice_item_count: 0,
              main_item_count: 18,
              expected_trial_count: 18,
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.click(screen.getByLabelText('Aggregation mode'));
    await user.selectOptions(screen.getByLabelText('Main banks'), ['stim_a', 'stim_b']);

    expect((await screen.findAllByText(/Selected main banks have mixed task families/)).length).toBeGreaterThan(0);
    expect(screen.getByLabelText('task family')).toHaveValue('mixed task families (invalid)');
    await user.click(screen.getByRole('button', { name: 'Create Run' }));
    const alerts = await screen.findAllByRole('alert');
    expect(alerts.some((item) => item.textContent?.includes('Selected main banks have mixed task families'))).toBe(true);
    expect(createSpy).not.toHaveBeenCalled();
  });

  it('blocks submit in multi mode when fewer than two main banks are selected', async () => {
    const user = userEvent.setup();
    const createSpy = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'scam_detection', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_a', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 10 },
              { stimulus_set_id: 'stim_b', name: 'Main B', task_family: 'scam_detection', validation_status: 'valid', n_items: 8 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs') && init?.method === 'POST') {
          createSpy();
          return new Response(JSON.stringify({ run_id: 'run_new' }), { status: 200 });
        }
        if (url.endsWith('/runs/preview')) {
          return new Response(
            JSON.stringify({
              resolved_task_family: 'scam_detection',
              validation_errors: ['multi aggregation_mode requires at least two main stimulus_set_ids'],
              operator_warnings: [],
              practice_item_count: 0,
              main_item_count: 10,
              expected_trial_count: 10,
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.click(screen.getByLabelText('Aggregation mode'));
    await user.selectOptions(screen.getByLabelText('Main banks'), ['stim_a']);
    await user.click(screen.getByRole('button', { name: 'Create Run' }));

    const alerts = await screen.findAllByRole('alert');
    expect(alerts.some((item) => item.textContent?.includes('multi aggregation_mode requires at least two main stimulus_set_ids'))).toBe(true);
    expect(createSpy).not.toHaveBeenCalled();
  });

  it('surfaces preview endpoint failures and clears stale preview values', async () => {
    const user = userEvent.setup();
    let previewCalls = 0;
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
          return new Response(
            JSON.stringify([{ stimulus_set_id: 'stim_a', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 10 }]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/preview')) {
          previewCalls += 1;
          if (previewCalls === 1) {
            return new Response(
              JSON.stringify({
                resolved_task_family: 'scam_detection',
                validation_errors: [],
                operator_warnings: [],
                practice_item_count: 1,
                main_item_count: 10,
                expected_trial_count: 11,
              }),
              { status: 200 },
            );
          }
          return new Response(JSON.stringify({ detail: 'preview backend unavailable' }), { status: 503 });
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    expect(await screen.findByText('Expected trial count: 11')).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText('run name'), '-updated');

    const alerts = await screen.findAllByRole('alert');
    expect(alerts.some((item) => item.textContent?.includes('Run preview is currently unavailable'))).toBe(true);
    expect(alerts.some((item) => item.textContent?.includes('preview backend unavailable'))).toBe(true);
    await waitFor(() => expect(screen.getByText('Expected trial count: 0')).toBeInTheDocument());
  });

  it('shows explicit unset task family and blocks submit when no main bank is selected', async () => {
    const user = userEvent.setup();
    const createSpy = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'default_family', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_a', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 10 },
              { stimulus_set_id: 'stim_b', name: 'Main B', task_family: 'scam_detection', validation_status: 'valid', n_items: 8 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs') && init?.method === 'POST') {
          createSpy();
          return new Response(JSON.stringify({ run_id: 'run_new' }), { status: 200 });
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.click(screen.getByLabelText('Aggregation mode'));
    await user.deselectOptions(screen.getByLabelText('Main banks'), ['stim_a']);

    expect(screen.getByLabelText('task family')).toHaveValue('no main bank selected');
    expect(screen.getByText('Main bank(s): none')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create Run' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Select at least one main bank before creating a run. Practice bank is optional and supplementary only.',
    );
    expect(createSpy).not.toHaveBeenCalled();
  });

  it('blocks submit when only a practice bank is selected and no main bank is selected', async () => {
    const user = userEvent.setup();
    const createSpy = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'default_family', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_main', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 10 },
              { stimulus_set_id: 'stim_practice', name: 'Practice A', task_family: 'scam_detection', validation_status: 'valid', n_items: 6 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs') && init?.method === 'POST') {
          createSpy();
          return new Response(JSON.stringify({ run_id: 'run_new' }), { status: 200 });
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    await user.selectOptions(screen.getByDisplayValue('Practice bank (optional supplementary)'), 'stim_practice');
    await user.click(screen.getByLabelText('Aggregation mode'));
    await user.deselectOptions(screen.getByLabelText('Main banks'), ['stim_main']);
    await user.click(screen.getByRole('button', { name: 'Create Run' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Select at least one main bank before creating a run. Practice bank is optional and supplementary only.',
    );
    expect(createSpy).not.toHaveBeenCalled();
  });

  it('allows submit when a main bank is selected and practice bank remains optional supplementary', async () => {
    const user = userEvent.setup();
    const createPayloadRef: { value: Record<string, unknown> | null } = { value: null };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'default_family', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_main', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 10 },
              { stimulus_set_id: 'stim_practice', name: 'Practice A', task_family: 'scam_detection', validation_status: 'valid', n_items: 6 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs') && init?.method === 'POST') {
          createPayloadRef.value = JSON.parse(String(init.body ?? '{}')) as Record<string, unknown>;
          return new Response(JSON.stringify({ run_id: 'run_new', run_name: 'run-new', public_slug: 'run-new', status: 'draft' }), { status: 200 });
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        if (url.endsWith('/runs/run_new')) return new Response(JSON.stringify({ run_id: 'run_new', run_name: 'run-new', status: 'draft' }), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.selectOptions(screen.getByDisplayValue('Practice bank (optional supplementary)'), 'stim_practice');
    await user.click(screen.getByRole('button', { name: 'Create Run' }));

    await waitFor(() => expect(createPayloadRef.value).not.toBeNull());
    if (!createPayloadRef.value) {
      throw new Error('Expected create payload to be captured');
    }
    const payload = createPayloadRef.value;
    expect(payload.stimulus_set_ids).toEqual(['stim_main']);
    expect(payload.practice_stimulus_set_id).toBe('stim_practice');
  });

  it('keeps one authoritative main-bank selection when switching between single and multi modes', async () => {
    const user = userEvent.setup();
    const createPayloadRef: { value: Record<string, unknown> | null } = { value: null };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'default_family', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_one', name: 'Main One', task_family: 'scam_detection', validation_status: 'valid', n_items: 10 },
              { stimulus_set_id: 'stim_two', name: 'Main Two', task_family: 'scam_detection', validation_status: 'valid', n_items: 8 },
              { stimulus_set_id: 'stim_three', name: 'Main Three', task_family: 'scam_detection', validation_status: 'valid', n_items: 6 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs') && init?.method === 'POST') {
          createPayloadRef.value = JSON.parse(String(init.body ?? '{}')) as Record<string, unknown>;
          return new Response(JSON.stringify({ run_id: 'run_new', run_name: 'run-new', public_slug: 'run-new', status: 'draft' }), { status: 200 });
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        if (url.endsWith('/runs/run_new')) return new Response(JSON.stringify({ run_id: 'run_new', run_name: 'run-new', status: 'draft' }), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    await user.click(screen.getByLabelText('Aggregation mode'));
    const multiSelect = screen.getByLabelText('Main banks');
    await user.selectOptions(multiSelect, ['stim_two', 'stim_three']);
    expect(screen.getByText('Main bank(s): Main One (10), Main Two (8), Main Three (6)')).toBeInTheDocument();

    await user.click(screen.getByLabelText('Aggregation mode'));

    const singleSelect = screen.getByLabelText('Main bank');
    expect(singleSelect).toHaveValue('stim_one');
    expect(screen.getByText('Main bank(s): Main One (10)')).toBeInTheDocument();
    expect(screen.getByLabelText('task family')).toHaveValue('scam_detection');
    expect(screen.getByText(/Selected stimulus set: Main One/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Create Run' }));
    await waitFor(() => expect(createPayloadRef.value).not.toBeNull());
    if (!createPayloadRef.value) {
      throw new Error('Expected create payload to be captured');
    }
    const payload = createPayloadRef.value;
    expect(payload.stimulus_set_ids).toEqual(['stim_one']);
  });

  it('renders only the single main-bank control in single mode and updates authoritative selection', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'default_family', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_a', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 10 },
              { stimulus_set_id: 'stim_b', name: 'Main B', task_family: 'claim_review', validation_status: 'valid', n_items: 8 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));

    expect(screen.getByLabelText('Main bank')).toBeInTheDocument();
    expect(screen.queryByLabelText('Main banks')).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText('Main bank'), 'stim_b');
    expect(screen.getByText('Main bank(s): Main B (8)')).toBeInTheDocument();
    expect(screen.getByLabelText('task family')).toHaveValue('claim_review');
  });

  it('renders only the multi main-bank control in multi mode and supports multiple selections', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'default_family', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(
            JSON.stringify([
              { stimulus_set_id: 'stim_a', name: 'Main A', task_family: 'scam_detection', validation_status: 'valid', n_items: 10 },
              { stimulus_set_id: 'stim_b', name: 'Main B', task_family: 'scam_detection', validation_status: 'valid', n_items: 8 },
              { stimulus_set_id: 'stim_c', name: 'Main C', task_family: 'scam_detection', validation_status: 'valid', n_items: 6 },
            ]),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.click(screen.getByLabelText('Aggregation mode'));

    expect(screen.queryByLabelText('Main bank')).not.toBeInTheDocument();
    const multiSelect = screen.getByLabelText('Main banks');
    await user.selectOptions(multiSelect, ['stim_a', 'stim_b', 'stim_c']);
    expect(screen.getByText('Main bank(s): Main A (10), Main B (8), Main C (6)')).toBeInTheDocument();
  });

  it('renders dashboard launch blockers and routes next actions to workflow pages', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/dashboard')) {
          return new Response(
            JSON.stringify({
              global_snapshot: {
                run_counts: { total: 1, draft: 1, active: 0, paused: 0, closed: 0 },
                session_counts: { total: 2, in_progress: 1, awaiting_final_submit: 1, finalized: 0 },
              },
              focus_run_snapshot: {
                run_id: 'run_blocked',
                public_slug: 'blocked-run',
                status: 'draft',
                launchable: false,
                launchability_reason: 'main bank required before activation',
                counts: { in_progress: 1, awaiting_final_submit: 1, finalized: 0 },
                stale_session_count: 1,
                export_availability: { state: 'empty', available_artifact_count: 0, artifact_count: 0 },
                warnings: ['Potential stale sessions: 1', 'Budget tolerance warning'],
                next_actions: [
                  { action: 'inspect_run', page: 'run', target_run_id: 'run_blocked' },
                ],
              },
              blockers: [
                {
                  kind: 'launchability',
                  severity: 'error',
                  run_id: 'run_blocked',
                  public_slug: 'blocked-run',
                  run_status: 'draft',
                  reason: 'main bank required before activation',
                },
              ],
              warnings: ['Potential stale sessions: 1', 'Budget tolerance warning'],
              next_actions: [{ action: 'inspect_run', page: 'run', target_run_id: 'run_blocked' }],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'scam_detection', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'RU' }));

    expect(await screen.findByText('Центр готовности к запуску')).toBeInTheDocument();
    expect((await screen.findAllByText('Блокеры запуска')).length).toBeGreaterThan(0);
    expect(screen.getByText('main bank required before activation')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Обновить дашборд' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Проверить запуск (run_blocked)' }));
    expect(await screen.findByText('Операции запуска')).toBeInTheDocument();
  });

  it('preserves dashboard target run context when navigating to run operations', async () => {
    const user = userEvent.setup();
    const fetchCalls: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        fetchCalls.push(url);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/dashboard')) {
          return new Response(
            JSON.stringify({
              global_snapshot: { run_counts: { total: 1, draft: 1, active: 0, paused: 0, closed: 0 }, session_counts: { total: 0, in_progress: 0 } },
              focus_run_snapshot: { run_id: 'run_focus', next_actions: [{ action: 'inspect_run', page: 'run', target_run_id: 'run_focus' }] },
              blockers: [],
              next_actions: [{ action: 'inspect_run', page: 'run', target_run_id: 'run_focus' }],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'scam_detection', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) return new Response(JSON.stringify([]), { status: 200 });
        if (url.endsWith('/runs')) {
          return new Response(JSON.stringify([{ run_id: 'run_focus', run_name: 'Focused run', public_slug: 'focused', status: 'draft', launchable: false }]), { status: 200 });
        }
        if (url.endsWith('/runs/run_focus')) {
          return new Response(JSON.stringify({ run_id: 'run_focus', run_name: 'Focused run', status: 'draft', run_status: 'draft' }), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Inspect run (run_focus)' }));
    expect(await screen.findByText('Run Operations')).toBeInTheDocument();
    await waitFor(() => expect(fetchCalls.some((url) => url.endsWith('/runs/run_focus'))).toBe(true));
  });

  it('preserves dashboard target run context when navigating to diagnostics', async () => {
    const user = userEvent.setup();
    const fetchCalls: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        fetchCalls.push(url);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/dashboard')) {
          return new Response(
            JSON.stringify({
              global_snapshot: { run_counts: { total: 1, draft: 0, active: 1, paused: 0, closed: 0 }, session_counts: { total: 0, in_progress: 0 } },
              focus_run_snapshot: { run_id: 'run_diag', next_actions: [{ action: 'open_diagnostics', page: 'diagnostics', target_run_id: 'run_diag' }] },
              blockers: [],
              next_actions: [{ action: 'open_diagnostics', page: 'diagnostics', target_run_id: 'run_diag' }],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs')) {
          return new Response(JSON.stringify([{ run_id: 'run_diag', run_name: 'Diagnostics run', public_slug: 'diag', status: 'active', launchable: true }]), { status: 200 });
        }
        if (url.endsWith('/runs/run_diag/diagnostics')) {
          return new Response(
            JSON.stringify({
              session_count_total: 0,
              trial_count_total: 0,
              warnings: ['Missing summary rows for one session.'],
              budget_tolerance_flags: [{ severity: 'warning', kind: 'missing_reference', condition: 'high_risk', message: 'No contract reference found.' }],
            }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Open diagnostics (run_diag)' }));
    expect(await screen.findByRole('heading', { name: 'Diagnostics' })).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveValue('run_diag');
    await user.click(screen.getByRole('button', { name: 'Load Diagnostics' }));
    await waitFor(() => expect(fetchCalls.some((url) => url.endsWith('/runs/run_diag/diagnostics'))).toBe(true));
    expect(await screen.findByRole('heading', { name: 'Operator view' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Warning messages' })).toBeInTheDocument();
    expect(screen.getAllByText('Missing summary rows for one session.').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Budget tolerance flags' })).toBeInTheDocument();
    expect(screen.getByText('missing_reference')).toBeInTheDocument();
    expect(screen.getByText('Technical/debug payload (JSON)')).toBeInTheDocument();
  });

  it('localizes canonical dashboard action keys in EN and RU without backend label fallback', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/dashboard')) {
          return new Response(
            JSON.stringify({
              global_snapshot: {
                run_counts: { total: 1, draft: 1, active: 0, paused: 0, closed: 0 },
                session_counts: { total: 0, in_progress: 0, awaiting_final_submit: 0, finalized: 0 },
              },
              focus_run_snapshot: {
                run_id: 'run_actions',
                public_slug: 'actions-run',
                status: 'draft',
                accepting_sessions_now: false,
                activation_ready: true,
                activation_readiness_reason: 'run is draft and ready to activate',
                launchable: false,
                launchability_reason: 'run is draft; activate to accept new participant sessions',
                counts: {},
                stale_session_count: 0,
                export_availability: { state: 'empty', available_artifact_count: 0, artifact_count: 0 },
                warnings: [],
                next_actions: [
                  { action: 'activate_run', page: 'run', target_run_id: 'run_actions' },
                  { action: 'inspect_run', page: 'run', target_run_id: 'run_actions' },
                  { action: 'monitor_sessions', page: 'sessions', target_run_id: 'run_actions' },
                  { action: 'open_diagnostics', page: 'diagnostics', target_run_id: 'run_actions' },
                  { action: 'download_exports', page: 'exports', target_run_id: 'run_actions' },
                ],
              },
              blockers: [],
              warnings: [],
              next_actions: [
                { action: 'activate_run', page: 'run', target_run_id: 'run_actions' },
                { action: 'inspect_run', page: 'run', target_run_id: 'run_actions' },
                { action: 'monitor_sessions', page: 'sessions', target_run_id: 'run_actions' },
                { action: 'open_diagnostics', page: 'diagnostics', target_run_id: 'run_actions' },
                { action: 'download_exports', page: 'exports', target_run_id: 'run_actions' },
              ],
            }),
            { status: 200 },
          );
        }
        if (url.endsWith('/runs/defaults')) {
          return new Response(JSON.stringify({ experiment_id: 'exp_1', task_family: 'scam_detection', config_preset_options: [] }), { status: 200 });
        }
        if (url.endsWith('/stimuli')) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');

    expect(screen.getByRole('button', { name: 'Activate run (run_actions)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Inspect run (run_actions)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Monitor sessions (run_actions)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open diagnostics (run_actions)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download exports (run_actions)' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'RU' }));

    expect(screen.getByRole('button', { name: 'Активировать запуск (run_actions)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Проверить запуск (run_actions)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Мониторить сессии (run_actions)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Открыть диагностику (run_actions)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Скачать экспорт (run_actions)' })).toBeInTheDocument();
  });

  it('renders activate_run only when backend marks the focus run activation-ready', async () => {
    const user = userEvent.setup();
    let dashboardCalls = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/dashboard')) {
          dashboardCalls += 1;
          if (dashboardCalls === 1) {
            return new Response(
              JSON.stringify({
                global_snapshot: { run_counts: { total: 1, draft: 1, active: 0, paused: 0, closed: 0 }, session_counts: { total: 0, in_progress: 0 } },
                focus_run_snapshot: {
                  run_id: 'run_not_ready',
                  status: 'draft',
                  accepting_sessions_now: false,
                  activation_ready: false,
                  activation_readiness_reason: 'missing config',
                  launchable: true,
                  launchability_reason: 'legacy field should not drive dashboard actions',
                  next_actions: [{ action: 'inspect_run', page: 'run', target_run_id: 'run_not_ready' }],
                },
                blockers: [{ kind: 'launchability', severity: 'error', run_id: 'run_not_ready', run_status: 'draft', reason: 'missing config' }],
                warnings: [],
                next_actions: [{ action: 'inspect_run', page: 'run', target_run_id: 'run_not_ready' }],
              }),
              { status: 200 },
            );
          }
          return new Response(
            JSON.stringify({
              global_snapshot: { run_counts: { total: 1, draft: 1, active: 0, paused: 0, closed: 0 }, session_counts: { total: 0, in_progress: 0 } },
              focus_run_snapshot: {
                run_id: 'run_ready',
                status: 'paused',
                accepting_sessions_now: false,
                activation_ready: true,
                activation_readiness_reason: 'run is paused and ready to activate',
                launchable: false,
                launchability_reason: 'run is paused; activate to accept new participant sessions',
                next_actions: [
                  { action: 'activate_run', page: 'run', target_run_id: 'run_ready' },
                  { action: 'inspect_run', page: 'run', target_run_id: 'run_ready' },
                ],
              },
              blockers: [],
              warnings: [],
              next_actions: [
                { action: 'activate_run', page: 'run', target_run_id: 'run_ready' },
                { action: 'inspect_run', page: 'run', target_run_id: 'run_ready' },
              ],
            }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    expect(screen.queryByRole('button', { name: 'Activate run (run_not_ready)' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Refresh dashboard' }));
    expect(await screen.findByRole('button', { name: 'Activate run (run_ready)' })).toBeInTheDocument();
  });

  it('keeps global launch-blocker count truthful when blocker cards are visually capped', async () => {
    const user = userEvent.setup();
    const blockers = Array.from({ length: 10 }, (_, index) => ({
      kind: 'launchability',
      severity: 'error',
      run_id: `run_blocked_${index}`,
      public_slug: `blocked-${index}`,
      run_status: 'draft',
      reason: `blocker reason ${index}`,
    }));

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/auth/me')) {
          return new Response(JSON.stringify({ authenticated: true, user: { user_id: 'u1', username: 'admin', is_admin: true } }), { status: 200 });
        }
        if (url.endsWith('/dashboard')) {
          return new Response(
            JSON.stringify({
              global_snapshot: {
                run_counts: { total: 10, draft: 10, active: 0, paused: 0, closed: 0 },
                session_counts: { total: 0, in_progress: 0, awaiting_final_submit: 0, finalized: 0 },
              },
              focus_run_snapshot: null,
              blockers,
              warnings: [],
              next_actions: [],
            }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify([]), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'RU' }));
    await screen.findByText('Центр готовности к запуску');

    const launchBlockersLabel = (await screen.findAllByText('Блокеры запуска', { selector: '.summary-card__label' }))[0];
    expect(within(launchBlockersLabel.closest('.summary-card') as HTMLElement).getByText('10')).toBeInTheDocument();

    expect(screen.getByText('run_blocked_0')).toBeInTheDocument();
    expect(screen.getByText('run_blocked_7')).toBeInTheDocument();
    expect(screen.queryByText('run_blocked_8')).not.toBeInTheDocument();
    expect(screen.queryByText('run_blocked_9')).not.toBeInTheDocument();
  });

});
