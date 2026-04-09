import React from 'react';

import { LanguageSwitcher } from './components/LanguageSwitcher';
import { Nav, type PageKey } from './components/Nav';
import { LocaleProvider, useLocale } from './i18n/useLocale';
import { useResearcherShell } from './hooks/useResearcherShell';
import { DashboardPage } from './pages/DashboardPage';
import { DiagnosticsPage } from './pages/DiagnosticsPage';
import { ExportsPage } from './pages/ExportsPage';
import { RunBuilderPage } from './pages/RunBuilderPage';
import { SessionMonitorPage } from './pages/SessionMonitorPage';
import { StimulusUploadPage } from './pages/StimulusUploadPage';

function ResearcherPageContent({
  page,
  onNavigate,
}: {
  page: PageKey;
  onNavigate: (page: PageKey) => void;
}) {
  if (page === 'dashboard') return <DashboardPage onNavigate={onNavigate} />;
  if (page === 'upload') return <StimulusUploadPage />;
  if (page === 'run') return <RunBuilderPage />;
  if (page === 'sessions') return <SessionMonitorPage />;
  if (page === 'diagnostics') return <DiagnosticsPage />;
  return <ExportsPage />;
}

function AppBody() {
  const { t } = useLocale();
  const shell = useResearcherShell(t);

  if (shell.authState === 'loading') {
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

  if (!shell.canRenderCabinet) {
    return (
      <main>
        <div className="toolbar">
          <LanguageSwitcher />
        </div>
        <h1>{t('app.title')}</h1>
        <section className="panel">
          <h2>{t('auth.loginTitle')}</h2>
          <p className="muted">{t('auth.loginHint')}</p>
          <form className="form-row" onSubmit={shell.submitLogin}>
            <label>
              {t('auth.username')}
              <input
                value={shell.username}
                onChange={(event) => shell.setUsername(event.target.value)}
              />
            </label>
            <label>
              {t('auth.password')}
              <input
                type="password"
                value={shell.password}
                onChange={(event) => shell.setPassword(event.target.value)}
              />
            </label>
            <button className="primary-btn" type="submit">
              {t('auth.login')}
            </button>
          </form>
          {shell.authError && (
            <p role="alert" className="alert-error">
              {shell.authError}
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
          {t('auth.loggedInAs')}: {shell.authedUsername}
        </p>
        <button className="secondary-btn" onClick={shell.submitLogout}>
          {t('auth.logout')}
        </button>
      </section>
      <Nav page={shell.page} setPage={shell.setPage} />
      <ResearcherPageContent page={shell.page} onNavigate={shell.setPage} />
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