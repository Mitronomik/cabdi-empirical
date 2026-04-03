import React, { useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { apiGet } from '../lib/api';

export function ExportsPage() {
  const [runId, setRunId] = useState('');
  const [response, setResponse] = useState('');
  const { t } = useLocale();

  async function load() {
    const out = await apiGet(`/admin/api/v1/runs/${runId}/exports`);
    setResponse(JSON.stringify(out, null, 2));
  }

  return (
    <section>
      <h2>{t('exports.title')}</h2>
      <input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder={t('exports.runId')} />
      <button onClick={load}>{t('exports.load')}</button>
      <pre>{response}</pre>
    </section>
  );
}
