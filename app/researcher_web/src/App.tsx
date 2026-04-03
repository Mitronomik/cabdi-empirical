import React, { useState } from 'react';

import { LanguageSwitcher } from './components/LanguageSwitcher';
import { Nav, type PageKey } from './components/Nav';
import { LocaleProvider, useLocale } from './i18n/useLocale';
import { DiagnosticsPage } from './pages/DiagnosticsPage';
import { ExportsPage } from './pages/ExportsPage';
import { RunBuilderPage } from './pages/RunBuilderPage';
import { SessionMonitorPage } from './pages/SessionMonitorPage';
import { StimulusUploadPage } from './pages/StimulusUploadPage';

function AppBody() {
  const [page, setPage] = useState<PageKey>('upload');
  const { t } = useLocale();

  return (
    <main>
      <LanguageSwitcher />
      <h1>{t('app.title')}</h1>
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
