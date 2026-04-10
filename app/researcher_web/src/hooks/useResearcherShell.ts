import { useEffect, useMemo, useState, type FormEvent } from 'react';

import { localizeOperatorError } from '../i18n/uiText';
import type { useLocale } from '../i18n/useLocale';
import { ApiHttpError, getCurrentUser, login, logout } from '../lib/api';
import type { PageKey } from '../components/Nav';

export type AuthState = 'loading' | 'authenticated' | 'unauthenticated' | 'service_unavailable';

export function useResearcherShell(t: ReturnType<typeof useLocale>['t']) {
  const [page, setPage] = useState<PageKey>('dashboard');
  const [authState, setAuthState] = useState<AuthState>('loading');
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authedUsername, setAuthedUsername] = useState<string>('');

  useEffect(() => {
    const loadAuth = async () => {
      try {
        const me = await getCurrentUser();
        setAuthedUsername(me.user.username);
        setAuthState('authenticated');
      } catch (error) {
        if (error instanceof ApiHttpError && error.status === 401) {
          setAuthState('unauthenticated');
          return;
        }
        setAuthError(localizeOperatorError(t, error));
        setAuthState('service_unavailable');
      }
    };
    void loadAuth();
  }, []);

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthError(null);
    try {
      const response = await login(username, password);
      setAuthedUsername(response.user.username);
      setPassword('');
      setAuthState('authenticated');
    } catch (error) {
      setAuthError(localizeOperatorError(t, error));
    }
  }

  async function submitLogout() {
    await logout();
    setAuthedUsername('');
    setAuthState('unauthenticated');
  }

  const canRenderCabinet = useMemo(() => authState === 'authenticated', [authState]);

  return {
    page,
    setPage,
    authState,
    username,
    setUsername,
    password,
    setPassword,
    authError,
    authedUsername,
    canRenderCabinet,
    submitLogin,
    submitLogout,
  };
}
