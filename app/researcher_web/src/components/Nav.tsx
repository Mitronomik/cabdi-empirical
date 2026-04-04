import React from 'react';

import { useLocale } from '../i18n/useLocale';

export type PageKey = 'upload' | 'run' | 'sessions' | 'diagnostics' | 'exports';

const pageKey: Record<PageKey, 'nav.upload' | 'nav.run' | 'nav.sessions' | 'nav.diagnostics' | 'nav.exports'> = {
  upload: 'nav.upload',
  run: 'nav.run',
  sessions: 'nav.sessions',
  diagnostics: 'nav.diagnostics',
  exports: 'nav.exports',
};

const pageStepKey: Record<PageKey, 'nav.step1' | 'nav.step2' | 'nav.step3' | 'nav.step4' | 'nav.step5'> = {
  upload: 'nav.step1',
  run: 'nav.step2',
  sessions: 'nav.step3',
  diagnostics: 'nav.step4',
  exports: 'nav.step5',
};

export function Nav({ page, setPage }: { page: PageKey; setPage: (p: PageKey) => void }) {
  const pages: PageKey[] = ['upload', 'run', 'sessions', 'diagnostics', 'exports'];
  const { t } = useLocale();

  return (
    <nav aria-label={t('nav.workflow')}>
      <p>{t('nav.workflow')}</p>
      {pages.map((p) => (
        <button key={p} onClick={() => setPage(p)} disabled={p === page} style={{ marginRight: 8 }}>
          {t(pageStepKey[p])}: {t(pageKey[p])}
        </button>
      ))}
    </nav>
  );
}
