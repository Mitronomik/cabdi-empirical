import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from '../App';

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.unstubAllGlobals();
  Object.defineProperty(window.navigator, 'language', {
    configurable: true,
    value: 'en-US',
  });
});

describe('researcher web shell', () => {
  it('renders admin title and language switcher', () => {
    render(<App />);
    expect(screen.getByText('CABDI Researcher Admin (MVP)')).toBeInTheDocument();
    expect(screen.getByLabelText(/language switcher/i)).toBeInTheDocument();

    const nav = screen.getByRole('navigation');
    expect(within(nav).getByRole('button', { name: 'Upload' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Load Recent' })).toBeInTheDocument();
  });

  it('switches UI copy when locale changes', async () => {
    render(<App />);
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: 'RU' }));
    expect(screen.getByText('Панель исследователя CABDI (MVP)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Загрузка' })).toBeInTheDocument();
  });

  it('defaults to browser locale when no saved locale exists', () => {
    Object.defineProperty(window.navigator, 'language', {
      configurable: true,
      value: 'ru-RU',
    });

    render(<App />);
    expect(screen.getByText('Панель исследователя CABDI (MVP)')).toBeInTheDocument();
  });

  it('saved locale persists across remounts and overrides browser locale', async () => {
    Object.defineProperty(window.navigator, 'language', {
      configurable: true,
      value: 'en-US',
    });

    const user = userEvent.setup();
    const { unmount } = render(<App />);
    await user.click(screen.getByRole('button', { name: 'RU' }));
    expect(screen.getByText('Панель исследователя CABDI (MVP)')).toBeInTheDocument();

    unmount();
    Object.defineProperty(window.navigator, 'language', {
      configurable: true,
      value: 'en-US',
    });
    render(<App />);
    expect(screen.getByText('Панель исследователя CABDI (MVP)')).toBeInTheDocument();
  });

  it('uses current pilot defaults in run builder', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            experiment_id: 'pilot_scam_not_scam_v1',
            task_family: 'scam_not_scam',
            config_preset_options: [{ preset_id: 'default_experiment', config: {} }],
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Run Builder' }));

    expect(await screen.findByDisplayValue('pilot_scam_not_scam_v1')).toBeInTheDocument();
    expect(screen.getByDisplayValue('scam_not_scam')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Load Recent' })).toBeInTheDocument();
  });

  it('renders upload success summary and refreshed recent stimulus list', async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify([{ stimulus_set_id: 'stim_old', name: 'old', task_family: 'scam_not_scam', n_items: 4 }]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            stimulus_set_id: 'stim_new',
            n_items: 2,
            validation_status: 'valid',
            warnings: [],
            errors: [],
            preview_rows: [{ stimulus_id: 's1' }],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([{ stimulus_set_id: 'stim_new', name: 'new', task_family: 'scam_not_scam', n_items: 2 }]),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      );
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    const file = new File(['{"x":1}\n'], 'stim.jsonl', { type: 'application/json' });
    await user.type(screen.getByPlaceholderText('stimulus set name'), 'new set');
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(fileInput, file);
    const form = document.querySelector('form') as HTMLFormElement;
    fireEvent.submit(form);

    expect(await screen.findByText('Upload result')).toBeInTheDocument();
    expect(screen.getByText(/stimulus_set_id: stim_new/)).toBeInTheDocument();
    expect(screen.getByText(/n_items: 2/)).toBeInTheDocument();
    expect(await screen.findByText(/stim_new · new/)).toBeInTheDocument();
  });

  it('uses selectors for run and monitor pages instead of manual run_id typing', async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ stimulus_set_id: 'stim_1', name: 'set', task_family: 'scam_not_scam' }]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            experiment_id: 'pilot_scam_not_scam_v1',
            task_family: 'scam_not_scam',
            config_preset_id: 'default_experiment',
            config_preset_options: [{ preset_id: 'default_experiment', config: { n_blocks: 3 } }],
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ run_id: 'run_1', public_slug: 'slug-1', task_family: 'scam_not_scam', linked_stimulus_set_ids: ['stim_1'] }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([{ run_id: 'run_1', run_name: 'run-1', public_slug: 'slug-1', task_family: 'scam_not_scam' }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ run_id: 'run_1', run_name: 'run-1' }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: 'run_1', counts: { created: 0 }, sessions: [] }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await user.click(screen.getByRole('button', { name: 'Run Builder' }));
    const createButton = await screen.findByRole('button', { name: 'Create Run' });
    await user.click(createButton);
    expect(await screen.findByText(/run_id: run_1/)).toBeInTheDocument();
    expect(screen.getByText(/linked stimulus sets/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Sessions' }));
    const selector = await screen.findByRole('combobox');
    expect(selector).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Load Sessions' }));
    expect(await screen.findByText(/"run_id": "run_1"/)).toBeInTheDocument();
  });
});
