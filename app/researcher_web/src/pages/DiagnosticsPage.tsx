import React, { useEffect, useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { getRunDiagnostics, listRuns } from '../lib/api';

export function DiagnosticsPage() {
  const [runId, setRunId] = useState('');
  const [response, setResponse] = useState('');
  const [runs, setRuns] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState('');
  const { t } = useLocale();

  useEffect(() => {
    void listRuns()
      .then((items) => {
        setRuns(items.slice(0, 10));
        if (items.length > 0) setRunId(String(items[0].run_id));
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unknown error'));
  }, []);

  async function load() {
    if (!runId) {
      setError('Select a run first.');
      return;
    }
    const out = await getRunDiagnostics(runId);
    setError('');
    setResponse(JSON.stringify(out, null, 2));
  }

  return (
    <section>
      <h2>{t('diagnostics.title')}</h2>
      {runs.length === 0 ? <p>No runs found. Create a run first.</p> : null}
      <select value={runId} onChange={(e) => setRunId(e.target.value)}>
        <option value="">{t('diagnostics.runId')}</option>
        {runs.map((run) => (
          <option key={String(run.run_id)} value={String(run.run_id)}>
            {String(run.run_id)} · {String(run.run_name)}
          </option>
        ))}
      </select>
      <button onClick={load}>{t('diagnostics.load')}</button>
      {error ? <p role="alert">{error}</p> : null}
      <pre>{response}</pre>
    </section>
  );
}
