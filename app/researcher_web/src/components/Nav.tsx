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

export function Nav({ page, setPage }: { page: PageKey; setPage: (p: PageKey) => void }) {
  const pages: PageKey[] = ['upload', 'run', 'sessions', 'diagnostics', 'exports'];
  const { t } = useLocale();

  return (
    <nav>
      {pages.map((p) => (
        <button key={p} onClick={() => setPage(p)} disabled={p === page} style={{ marginRight: 8 }}>
          {t(pageKey[p])}
        </button>
      ))}
    </nav>
  );
}
