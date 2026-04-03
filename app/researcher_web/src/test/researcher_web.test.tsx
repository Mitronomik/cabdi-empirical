import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import App from '../App';

afterEach(() => {
  cleanup();
  window.localStorage.clear();
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
});