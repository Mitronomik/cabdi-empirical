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
  const sessionCounts = ((data?.session_counts as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const conditionCounts = ((data?.completed_trials_per_condition as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const modelWrongShare = ((data?.model_wrong_share as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const groupedWarnings = useMemo(() => {
    const groups: Record<string, string[]> = {
      budget: [],
      data: [],
      verification: [],
      other: [],
    };
    warnings.forEach((warning) => {
      const text = String(warning);
      const lowered = text.toLowerCase();
      if (lowered.includes('budget')) groups.budget.push(text);
      else if (lowered.includes('missing') || lowered.includes('schema') || lowered.includes('field')) groups.data.push(text);
      else if (lowered.includes('verify') || lowered.includes('verification')) groups.verification.push(text);
      else groups.other.push(text);
    });
    return groups;
  }, [warnings]);
  const warningGroupMeta: Array<{ key: keyof typeof groupedWarnings; label: string }> = [
    { key: 'budget', label: 'Budget matching warnings' },
    { key: 'data', label: 'Data quality warnings' },
    { key: 'verification', label: 'Verification usage warnings' },
    { key: 'other', label: 'Other warnings' },
  ];

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
              <div className="stack-grid">
                {warningGroupMeta
                  .filter((group) => groupedWarnings[group.key].length > 0)
                  .map((group) => (
                    <article key={group.key} className="info-card info-card--warn">
                      <h4>{group.label}</h4>
                      <ul>
                        {groupedWarnings[group.key].map((warning, index) => (
                          <li key={`${group.key}-${index}`}>{warning}</li>
                        ))}
                      </ul>
                    </article>
                  ))}
              </div>
            ) : null}
          </section>
          <section className="panel">
            <h3>Operator view</h3>
            <div className="stack-grid">
              <article className="info-card">
                <h4>{t('diagnostics.sessionCounts')}</h4>
                {Object.keys(sessionCounts).length === 0 ? <p className="muted">{t('common.na')}</p> : null}
                {Object.entries(sessionCounts).map(([key, value]) => (
                  <p key={key}>
                    <StatusBadge label={localizeStatus(t, key)} tone="info" />: {String(value)}
                  </p>
                ))}
              </article>
              <article className="info-card">
                <h4>{t('diagnostics.completedTrialsPerCondition')}</h4>
                {Object.keys(conditionCounts).length === 0 ? <p className="muted">{t('common.na')}</p> : null}
                {Object.entries(conditionCounts).map(([key, value]) => (
                  <p key={key}>
                    <KbdMono>{key}</KbdMono>: {String(value)}
                  </p>
                ))}
              </article>
              <article className="info-card">
                <h4>{t('diagnostics.modelWrongShare')}</h4>
                {Object.keys(modelWrongShare).length === 0 ? <p className="muted">{t('common.na')}</p> : null}
                {Object.entries(modelWrongShare).map(([key, value]) => (
                  <p key={key}>
                    <KbdMono>{key}</KbdMono>: {String(value)}
                  </p>
                ))}
              </article>
            </div>
            <details className="details-panel">
              <summary>{t('diagnostics.detailsTitle')}</summary>
              <pre>{JSON.stringify(data, null, 2)}</pre>
            </details>
          </section>
        </>
      ) : (
        <p>{t('diagnostics.notLoaded')}</p>
      )}
    </section>
  );
}
