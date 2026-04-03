import React, { useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { apiGet } from '../lib/api';

export function DiagnosticsPage() {
  const [runId, setRunId] = useState('');
  const [response, setResponse] = useState('');
  const { t } = useLocale();

  async function load() {
    const out = await apiGet(`/admin/api/v1/runs/${runId}/diagnostics`);
    setResponse(JSON.stringify(out, null, 2));
  }

  return (
    <section>
      <h2>{t('diagnostics.title')}</h2>
      <input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder={t('diagnostics.runId')} />
      <button onClick={load}>{t('diagnostics.load')}</button>
      <pre>{response}</pre>
    </section>
  );
}
