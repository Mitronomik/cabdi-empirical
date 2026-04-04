import React, { useEffect, useMemo, useState } from 'react';

import { KbdMono, StatusBadge, SummaryCard } from '../components/OperatorPrimitives';
import { localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { getRunDiagnostics, listRuns } from '../lib/api';
import { parseRunSummary, pickDefaultRunId, runOptionLabelLocalized } from '../lib/researcherUi';

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
  const warnings = Array.isArray(data?.warnings) ? data?.warnings : [];

  return (
    <section>
      <h2>{t('diagnostics.title')}</h2>
      <p className="muted">{t('diagnostics.workflowHint')}</p>
      <section className="panel">
        <div className="toolbar">
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
          <button className="primary-btn" onClick={load} disabled={loadingDiagnostics || !runId}>
            {loadingDiagnostics ? t('common.loading') : t('diagnostics.load')}
          </button>
        </div>
        {selectedRun ? <p>{t('common.selectedRun')}: {runOptionLabelLocalized(selectedRun, (value) => localizeStatus(t, value))} · <KbdMono>{selectedRun.run_id}</KbdMono></p> : null}
      </section>
      {error ? (
        <p role="alert" className="alert-error">
          {error}
        </p>
      ) : null}
      {data ? (
        <>
          <section className="panel">
            <h3>{t('diagnostics.summaryTitle')}</h3>
            <div className="summary-grid">
              <SummaryCard label={t('diagnostics.totalSessions')} value={String(data.session_count_total ?? 0)} tone="info" />
              <SummaryCard label={t('diagnostics.totalTrials')} value={String(data.trial_count_total ?? 0)} tone="info" />
              <SummaryCard label={t('diagnostics.verificationRate')} value={String(data.verification_usage_rate ?? 0)} tone="warn" />
              <SummaryCard label={t('diagnostics.warningCount')} value={String(warnings.length)} tone={warnings.length > 0 ? 'bad' : 'good'} />
            </div>
          </section>
          <section className="panel">
            <h3>{t('diagnostics.warnings')}</h3>
            {warnings.length === 0 ? <StatusBadge label={t('diagnostics.noWarnings')} tone="good" /> : null}
            {warnings.length > 0 ? (
              <ul>
                {warnings.map((warning, index) => (
                  <li key={`${warning}-${index}`}>{String(warning)}</li>
                ))}
              </ul>
            ) : null}
          </section>
          <section className="panel">
            <h3>{t('diagnostics.detailsTitle')}</h3>
            <p>{t('diagnostics.sessionCounts')}: {JSON.stringify(data.session_counts ?? {}, null, 2)}</p>
            <p>{t('diagnostics.completedTrialsPerCondition')}: {JSON.stringify(data.completed_trials_per_condition ?? {}, null, 2)}</p>
            <p>{t('diagnostics.modelWrongShare')}: {JSON.stringify(data.model_wrong_share ?? {}, null, 2)}</p>
          </section>
        </>
      ) : (
        <p>{t('diagnostics.notLoaded')}</p>
      )}
    </section>
  );
}
