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
  selectedRunId,
  onSelectedRunIdChange,
}: {
  page: PageKey;
  onNavigate: (page: PageKey, targetRunId?: string) => void;
  selectedRunId: string;
  onSelectedRunIdChange: (runId: string) => void;
}) {
  if (page === 'dashboard') return <DashboardPage onNavigate={onNavigate} />;
  if (page === 'upload') return <StimulusUploadPage />;
  if (page === 'run') return <RunBuilderPage initialSelectedRunId={selectedRunId} onSelectedRunIdChange={onSelectedRunIdChange} />;
  if (page === 'sessions') return <SessionMonitorPage initialSelectedRunId={selectedRunId} onSelectedRunIdChange={onSelectedRunIdChange} />;
  if (page === 'diagnostics') return <DiagnosticsPage initialSelectedRunId={selectedRunId} onSelectedRunIdChange={onSelectedRunIdChange} />;
  return <ExportsPage initialSelectedRunId={selectedRunId} onSelectedRunIdChange={onSelectedRunIdChange} />;
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
    if (shell.authState === 'service_unavailable') {
      return (
        <main>
          <div className="toolbar">
            <LanguageSwitcher />
          </div>
          <h1>{t('app.title')}</h1>
          <section className="panel">
            <h2>{t('auth.serviceUnavailableTitle')}</h2>
            <p className="muted">{t('auth.serviceUnavailableHint')}</p>
            {shell.authError && (
              <p role="alert" className="alert-error">
                {shell.authError}
              </p>
            )}
            <button className="secondary-btn" onClick={() => window.location.reload()}>
              {t('auth.retry')}
            </button>
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
      <Nav page={shell.page} setPage={(page) => shell.navigateTo(page)} />
      <ResearcherPageContent
        page={shell.page}
        onNavigate={shell.navigateTo}
        selectedRunId={shell.selectedRunId}
        onSelectedRunIdChange={shell.setSelectedRunId}
      />
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
