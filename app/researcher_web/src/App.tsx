import React, { useEffect, useState } from 'react';

import { LanguageSwitcher } from './components/LanguageSwitcher';
import { Nav, type PageKey } from './components/Nav';
import { localizeOperatorError } from './i18n/uiText';
import { LocaleProvider, useLocale } from './i18n/useLocale';
import { getCurrentUser, login, logout } from './lib/api';
import { DashboardPage } from './pages/DashboardPage';
import { DiagnosticsPage } from './pages/DiagnosticsPage';
import { ExportsPage } from './pages/ExportsPage';
import { RunBuilderPage } from './pages/RunBuilderPage';
import { SessionMonitorPage } from './pages/SessionMonitorPage';
import { StimulusUploadPage } from './pages/StimulusUploadPage';

type AuthState = 'loading' | 'authenticated' | 'unauthenticated';

function AppBody() {
  const [page, setPage] = useState<PageKey>('dashboard');
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
        <div className="toolbar">
          <LanguageSwitcher />
        </div>
        <h1>{t('app.title')}</h1>
        <p>{t('auth.checking')}</p>
      </main>
    );
  }

  if (authState === 'unauthenticated') {
    return (
      <main>
        <div className="toolbar">
          <LanguageSwitcher />
        </div>
        <h1>{t('app.title')}</h1>
        <section className="panel">
          <h2>{t('auth.loginTitle')}</h2>
          <p className="muted">{t('auth.loginHint')}</p>
          <form
            className="form-row"
            onSubmit={async (event) => {
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
            <button className="primary-btn" type="submit">
              {t('auth.login')}
            </button>
          </form>
          {authError && (
            <p role="alert" className="alert-error">
              {authError}
            </p>
          )}
        </section>
      </main>
    );
  }

  return (
    <main>
      <div className="toolbar">
        <LanguageSwitcher />
      </div>
      <h1>{t('app.title')}</h1>
      <p>{t('app.subtitle')}</p>
      <section className="panel toolbar" aria-label={t('app.operatorSession')}>
        <p>
          {t('auth.loggedInAs')}: {authedUsername}
        </p>
        <button
          className="secondary-btn"
          onClick={async () => {
            await logout();
            setAuthedUsername('');
            setAuthState('unauthenticated');
          }}
        >
          {t('auth.logout')}
        </button>
      </section>
      <Nav page={page} setPage={setPage} />
      {page === 'dashboard' && <DashboardPage onNavigate={setPage} />}
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
