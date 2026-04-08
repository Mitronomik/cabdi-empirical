import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from '../App';

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
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.selectOptions(screen.getByDisplayValue('Practice bank (optional)'), 'stim_practice');

    const draftSummarySection = (await screen.findByText('Run summary before activation')).closest('section');
    expect(draftSummarySection).not.toBeNull();
    expect(within(draftSummarySection as HTMLElement).getByText('Total practice items: 6')).toBeInTheDocument();
    expect(within(draftSummarySection as HTMLElement).getByText('Total main items: 48')).toBeInTheDocument();
    expect(within(draftSummarySection as HTMLElement).getByText('Expected trial count: 54')).toBeInTheDocument();
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

    const detailsHeading = await screen.findByText('Run details');
    const detailsPanel = detailsHeading.closest('section');
    expect(detailsPanel).not.toBeNull();
    expect(within(detailsPanel as HTMLElement).getByText(/Run name: run-1/)).toBeInTheDocument();
    await user.click((await screen.findAllByRole('button', { name: 'Details' }))[1]);
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
    await user.click(await screen.findByRole('button', { name: 'Details' }));
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

    const copyButton = await screen.findByRole('button', { name: 'Copy link' });
    expect(copyButton).toBeEnabled();
    await user.click(copyButton);
    expect(clipboardWrite).toHaveBeenCalledWith('https://cabdi.local/r/run-1');
    expect(await screen.findByText('Participant link copied.')).toBeInTheDocument();
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

    const practiceSelect = screen.getByDisplayValue('Practice bank (optional)');
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
    await user.selectOptions(screen.getByDisplayValue('Practice bank (optional)'), 'stim_practice');

    expect(screen.queryByRole('option', { name: /Practice A • scam_detection • 6 • Valid/ })).not.toBeInTheDocument();

    await user.click(screen.getByLabelText('Aggregation mode'));
    const multiSelect = screen.getByRole('listbox');
    expect(within(multiSelect).queryByRole('option', { name: /Practice A/ })).not.toBeInTheDocument();
    expect(within(multiSelect).getByRole('option', { name: /Main A/ })).toBeInTheDocument();
  });

  it('single mode derives task family and payload from the selected main bank', async () => {
    const user = userEvent.setup();
    let createPayload: Record<string, unknown> | null = null;
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
          createPayload = JSON.parse(String(init.body ?? '{}')) as Record<string, unknown>;
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

    await user.selectOptions(screen.getByDisplayValue('Main Scam • scam_detection • 10 • Valid'), 'stim_claim');
    expect(screen.getByLabelText('task family')).toHaveValue('claim_review');
    expect(screen.getByText(/Selected stimulus set: Main Claim/)).toBeInTheDocument();
    expect(screen.getByText('Main bank(s): Main Claim (8)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create Run' }));

    await waitFor(() => expect(createPayload).not.toBeNull());
    expect(createPayload?.stimulus_set_ids).toEqual(['stim_claim']);
    expect(createPayload?.task_family).toBe('claim_review');
  });

  it('multi mode derives task family and payload from selected banks only when consistent', async () => {
    const user = userEvent.setup();
    let createPayload: Record<string, unknown> | null = null;
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
          createPayload = JSON.parse(String(init.body ?? '{}')) as Record<string, unknown>;
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
    const multiSelect = screen.getByRole('listbox');
    await user.deselectOptions(multiSelect, ['stim_single']);
    await user.selectOptions(multiSelect, ['stim_multi_a', 'stim_multi_b']);

    expect(screen.getByLabelText('task family')).toHaveValue('claim_review');
    expect(screen.queryByText(/Selected stimulus set:/)).not.toBeInTheDocument();
    expect(screen.getByText('Main bank(s): Multi A (8), Multi B (7)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create Run' }));

    await waitFor(() => expect(createPayload).not.toBeNull());
    expect(createPayload?.stimulus_set_ids).toEqual(['stim_multi_a', 'stim_multi_b']);
    expect(createPayload?.task_family).toBe('claim_review');
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
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.click(screen.getByLabelText('Aggregation mode'));
    await user.selectOptions(screen.getByRole('listbox'), ['stim_a', 'stim_b']);

    expect(await screen.findByText(/Selected main banks have mixed task families/)).toBeInTheDocument();
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
        if (url.endsWith('/runs')) return new Response(JSON.stringify([]), { status: 200 });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    render(<App />);
    await screen.findByText('Logged in as: admin');
    await user.click(screen.getByRole('button', { name: 'Step 2: Create & Control Runs' }));
    await user.click(screen.getByLabelText('Aggregation mode'));
    await user.selectOptions(screen.getByRole('listbox'), ['stim_a']);
    await user.click(screen.getByRole('button', { name: 'Create Run' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Aggregation mode requires selecting at least two main banks.');
    expect(createSpy).not.toHaveBeenCalled();
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
    await user.deselectOptions(screen.getByRole('listbox'), ['stim_a']);

    expect(screen.getByLabelText('task family')).toHaveValue('no main bank selected');
    expect(screen.getByText('Main bank(s): none')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create Run' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Select a validated stimulus set before creating a run.');
    expect(createSpy).not.toHaveBeenCalled();
  });

});
