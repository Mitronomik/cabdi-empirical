import React, { useEffect, useMemo, useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { getRunDiagnostics, listRuns } from '../lib/api';
import { parseRunSummary, pickDefaultRunId, runOptionLabel } from '../lib/researcherUi';

export function DiagnosticsPage() {
  const [runId, setRunId] = useState('');
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [runs, setRuns] = useState<Array<ReturnType<typeof parseRunSummary>>>([]);
  const [error, setError] = useState('');
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingDiagnostics, setLoadingDiagnostics] = useState(false);
  const { t } = useLocale();

  async function loadRuns() {
    setLoadingRuns(true);
    setError('');
    try {
      const items = (await listRuns()).slice(0, 30).map(parseRunSummary);
      setRuns(items);
      if (items.length > 0) setRunId((prev) => prev || pickDefaultRunId(items));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.unknownError'));
    } finally {
      setLoadingRuns(false);
    }
  }

  useEffect(() => {
    void loadRuns();
  }, []);

  async function load() {
    if (!runId) {
      setError(t('common.selectRunFirst'));
      return;
    }
    setLoadingDiagnostics(true);
    try {
      const out = await getRunDiagnostics(runId);
      setData(out);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.unknownError'));
    } finally {
      setLoadingDiagnostics(false);
    }
  }

  const selectedRun = useMemo(() => runs.find((run) => run.run_id === runId), [runId, runs]);

  return (
    <section>
      <h2>{t('diagnostics.title')}</h2>
      <p>{t('diagnostics.workflowHint')}</p>
      {loadingRuns ? <p>{t('common.loadingRuns')}</p> : null}
      {runs.length === 0 && !loadingRuns ? <p>{t('common.noRuns')}</p> : null}
      <select value={runId} onChange={(e) => setRunId(e.target.value)}>
        <option value="">{t('diagnostics.runId')}</option>
        {runs.map((run) => (
          <option key={run.run_id} value={run.run_id}>
            {runOptionLabel(run)}
          </option>
        ))}
      </select>
      <button onClick={load} disabled={loadingDiagnostics || !runId}>
        {loadingDiagnostics ? t('common.loading') : t('diagnostics.load')}
      </button>
      {selectedRun ? <p>{t('common.selectedRun')}: {runOptionLabel(selectedRun)} · {selectedRun.run_id}</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {data ? (
        <>
          <p>{t('diagnostics.totalSessions')}: {String(data.session_count_total ?? 0)}</p>
          <p>{t('diagnostics.totalTrials')}: {String(data.trial_count_total ?? 0)}</p>
          <p>{t('diagnostics.verificationRate')}: {String(data.verification_usage_rate ?? 0)}</p>
          <pre>session_counts: {JSON.stringify(data.session_counts ?? {}, null, 2)}</pre>
          <pre>completed_trials_per_condition: {JSON.stringify(data.completed_trials_per_condition ?? {}, null, 2)}</pre>
          <pre>model_wrong_share: {JSON.stringify(data.model_wrong_share ?? {}, null, 2)}</pre>
          <pre>warnings: {JSON.stringify(data.warnings ?? [], null, 2)}</pre>
        </>
      ) : (
        <p>{t('diagnostics.notLoaded')}</p>
      )}
    </section>
  );
}
