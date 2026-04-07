import { cleanup, render, screen, waitFor } from '@testing-library/react';
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

});
