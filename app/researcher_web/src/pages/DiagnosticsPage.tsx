import React, { useEffect, useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { getRunDiagnostics, listRuns } from '../lib/api';

export function DiagnosticsPage() {
  const [runId, setRunId] = useState('');
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [runs, setRuns] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState('');
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingDiagnostics, setLoadingDiagnostics] = useState(false);
  const { t } = useLocale();

  async function loadRuns() {
    setLoadingRuns(true);
    setError('');
    try {
      const items = await listRuns();
      setRuns(items.slice(0, 30));
      if (items.length > 0) setRunId((prev) => prev || String(items[0].run_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoadingRuns(false);
    }
  }

  useEffect(() => {
    void loadRuns();
  }, []);

  async function load() {
    if (!runId) {
      setError('Select a run first.');
      return;
    }
    setLoadingDiagnostics(true);
    try {
      const out = await getRunDiagnostics(runId);
      setData(out);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoadingDiagnostics(false);
    }
  }

  return (
    <section>
      <h2>{t('diagnostics.title')}</h2>
      {loadingRuns ? <p>Loading runs...</p> : null}
      {runs.length === 0 && !loadingRuns ? <p>No runs found. Create and activate a run first.</p> : null}
      <select value={runId} onChange={(e) => setRunId(e.target.value)}>
        <option value="">{t('diagnostics.runId')}</option>
        {runs.map((run) => (
          <option key={String(run.run_id)} value={String(run.run_id)}>
            {String(run.run_name)} · {String(run.public_slug)} · {String(run.status)}
          </option>
        ))}
      </select>
      <button onClick={load} disabled={loadingDiagnostics || !runId}>
        {loadingDiagnostics ? 'Loading...' : t('diagnostics.load')}
      </button>
      {error ? <p role="alert">{error}</p> : null}
      {data ? (
        <>
          <p>run_id: {String(data.run_id)}</p>
          <pre>session_counts: {JSON.stringify(data.session_counts ?? {}, null, 2)}</pre>
          <pre>completed_trials_per_condition: {JSON.stringify(data.completed_trials_per_condition ?? {}, null, 2)}</pre>
          <pre>model_wrong_share: {JSON.stringify(data.model_wrong_share ?? {}, null, 2)}</pre>
          <p>verification_usage_rate: {String(data.verification_usage_rate ?? 0)}</p>
          <p>reason_click_rate: {String(data.reason_click_rate ?? 0)}</p>
          <p>evidence_open_rate: {String(data.evidence_open_rate ?? 0)}</p>
          <pre>block_order_distribution: {JSON.stringify(data.block_order_distribution ?? {}, null, 2)}</pre>
          <pre>budget_tolerance_flags: {JSON.stringify(data.budget_tolerance_flags ?? [], null, 2)}</pre>
          <pre>warnings: {JSON.stringify(data.warnings ?? [], null, 2)}</pre>
        </>
      ) : null}
    </section>
  );
}
