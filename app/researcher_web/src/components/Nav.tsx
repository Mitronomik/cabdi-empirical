import React from 'react';

import { useLocale } from '../i18n/useLocale';

export type PageKey = 'dashboard' | 'upload' | 'run' | 'sessions' | 'diagnostics' | 'exports';

const pageKey: Record<
  PageKey,
  'nav.dashboard' | 'nav.upload' | 'nav.run' | 'nav.sessions' | 'nav.diagnostics' | 'nav.exports'
> = {
  dashboard: 'nav.dashboard',
  upload: 'nav.upload',
  run: 'nav.run',
  sessions: 'nav.sessions',
  diagnostics: 'nav.diagnostics',
  exports: 'nav.exports',
};

const pageStepKey: Record<PageKey, 'nav.step0' | 'nav.step1' | 'nav.step2' | 'nav.step3' | 'nav.step4' | 'nav.step5'> = {
  dashboard: 'nav.step0',
  upload: 'nav.step1',
  run: 'nav.step2',
  sessions: 'nav.step3',
  diagnostics: 'nav.step4',
  exports: 'nav.step5',
};

export function Nav({ page, setPage }: { page: PageKey; setPage: (p: PageKey) => void }) {
  const pages: PageKey[] = ['dashboard', 'upload', 'run', 'sessions', 'diagnostics', 'exports'];
  const { t } = useLocale();
  const shortLabel: Record<PageKey, string> = {
    dashboard: 'Dashboard',
    upload: 'Stimuli',
    run: 'Run setup',
    sessions: 'Sessions',
    diagnostics: 'Diagnostics',
    exports: 'Exports',
  };

  return (
    <nav aria-label={t('nav.workflow')} className="panel workflow-nav">
      <p className="workflow-nav__title">{t('nav.workflow')}</p>
      <div className="workflow-nav__rail">
        {pages.map((p) => (
          <button
            key={p}
            onClick={() => setPage(p)}
            disabled={p === page}
            aria-label={`${t(pageStepKey[p])}: ${t(pageKey[p])}`}
            className={p === page ? 'workflow-nav__item workflow-nav__item--active' : 'workflow-nav__item'}
          >
            <span className="workflow-nav__step">{t(pageStepKey[p])}</span>
            <span className="workflow-nav__label">{shortLabel[p]}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
