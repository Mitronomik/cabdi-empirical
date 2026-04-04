import React, { useEffect, useState } from 'react';

import { LanguageSwitcher } from './components/LanguageSwitcher';
import { Nav, type PageKey } from './components/Nav';
import { LocaleProvider, useLocale } from './i18n/useLocale';
import { getCurrentUser, login, logout } from './lib/api';
import { DiagnosticsPage } from './pages/DiagnosticsPage';
import { ExportsPage } from './pages/ExportsPage';
import { RunBuilderPage } from './pages/RunBuilderPage';
import { SessionMonitorPage } from './pages/SessionMonitorPage';
import { StimulusUploadPage } from './pages/StimulusUploadPage';

type AuthState = 'loading' | 'authenticated' | 'unauthenticated';

function AppBody() {
  const [page, setPage] = useState<PageKey>('upload');
  const [authState, setAuthState] = useState<AuthState>('loading');
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authedUsername, setAuthedUsername] = useState<string>('');
  const { t } = useLocale();

  useEffect(() => {
    const load = async () => {
      try {
        const me = await getCurrentUser();
        setAuthedUsername(me.user.username);
        setAuthState('authenticated');
      } catch {
        setAuthState('unauthenticated');
      }
    };
    void load();
  }, []);

  if (authState === 'loading') {
    return (
      <main>
        <LanguageSwitcher />
        <h1>{t('app.title')}</h1>
        <p>Checking auth...</p>
      </main>
    );
  }

  if (authState === 'unauthenticated') {
    return (
      <main>
        <LanguageSwitcher />
        <h1>{t('app.title')}</h1>
        <h2>{t('auth.loginTitle')}</h2>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            setAuthError(null);
            try {
              const response = await login(username, password);
              setAuthedUsername(response.user.username);
              setPassword('');
              setAuthState('authenticated');
            } catch (error) {
              setAuthError(error instanceof Error ? error.message : 'Login failed');
            }
          }}
        >
          <label>
            {t('auth.username')}
            <input value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label>
            {t('auth.password')}
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <button type="submit">{t('auth.login')}</button>
        </form>
        {authError && <p role="alert">{authError}</p>}
      </main>
    );
  }

  return (
    <main>
      <LanguageSwitcher />
      <h1>{t('app.title')}</h1>
      <p>{t('auth.loggedInAs')}: {authedUsername}</p>
      <button
        onClick={async () => {
          await logout();
          setAuthedUsername('');
          setAuthState('unauthenticated');
        }}
      >
        {t('auth.logout')}
      </button>
      <Nav page={page} setPage={setPage} />
      {page === 'upload' && <StimulusUploadPage />}
      {page === 'run' && <RunBuilderPage />}
      {page === 'sessions' && <SessionMonitorPage />}
      {page === 'diagnostics' && <DiagnosticsPage />}
      {page === 'exports' && <ExportsPage />}
    </main>
  );
}

function App() {
  return (
    <LocaleProvider>
      <AppBody />
    </LocaleProvider>
  );
}

export default App;
