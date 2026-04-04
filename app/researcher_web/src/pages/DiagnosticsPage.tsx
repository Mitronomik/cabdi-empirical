import React, { useEffect, useMemo, useState } from 'react';

import { localizeOperatorError } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { getRunDiagnostics, listRuns } from '../lib/api';
import { parseRunSummary, pickDefaultRunId, runOptionLabelLocalized } from '../lib/researcherUi';
import { localizeStatus } from '../i18n/uiText';

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
      setError(localizeOperatorError(t, err));
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
      setError(localizeOperatorError(t, err));
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
            {runOptionLabelLocalized(run, (value) => localizeStatus(t, value))}
          </option>
        ))}
      </select>
      <button onClick={load} disabled={loadingDiagnostics || !runId}>
        {loadingDiagnostics ? t('common.loading') : t('diagnostics.load')}
      </button>
      {selectedRun ? <p>{t('common.selectedRun')}: {runOptionLabelLocalized(selectedRun, (value) => localizeStatus(t, value))} · {selectedRun.run_id}</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {data ? (
        <>
          <p>{t('diagnostics.totalSessions')}: {String(data.session_count_total ?? 0)}</p>
          <p>{t('diagnostics.totalTrials')}: {String(data.trial_count_total ?? 0)}</p>
          <p>{t('diagnostics.verificationRate')}: {String(data.verification_usage_rate ?? 0)}</p>
          <pre>{t('diagnostics.sessionCounts')}: {JSON.stringify(data.session_counts ?? {}, null, 2)}</pre>
          <pre>{t('diagnostics.completedTrialsPerCondition')}: {JSON.stringify(data.completed_trials_per_condition ?? {}, null, 2)}</pre>
          <pre>{t('diagnostics.modelWrongShare')}: {JSON.stringify(data.model_wrong_share ?? {}, null, 2)}</pre>
          <pre>{t('diagnostics.warnings')}: {JSON.stringify(data.warnings ?? [], null, 2)}</pre>
        </>
      ) : (
        <p>{t('diagnostics.notLoaded')}</p>
      )}
    </section>
  );
}
