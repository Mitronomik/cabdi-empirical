import React, { useEffect, useMemo, useState } from 'react';

import { KbdMono, StatusBadge, SummaryCard } from '../components/OperatorPrimitives';
import { localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { getRunDiagnostics, listRuns } from '../lib/api';
import { buildDiagnosticIssues, groupOrder } from '../lib/diagnosticsUi';
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
  const sessionCounts = ((data?.session_counts as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const operationalSummary = ((data?.operational_summary as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const conditionCounts = ((data?.completed_trials_per_condition as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const modelWrongShare = ((data?.model_wrong_share as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const issues = useMemo(() => buildDiagnosticIssues(data), [data]);
  const groupedIssues = useMemo(() => {
    const groups = new Map<string, { label: string; items: typeof issues }>();
    for (const issue of issues) {
      const label =
        issue.group === 'dataQuality'
          ? 'Data quality problems'
          : issue.group === 'runShape'
            ? 'Run-shape problems'
            : issue.group === 'behavioralAnomaly'
              ? 'Behavioral anomalies'
              : issue.group === 'budgetContract'
                ? 'Budget-contract anomalies'
                : 'Other';
      const entry = groups.get(issue.group);
      if (entry) entry.items.push(issue);
      else groups.set(issue.group, { label, items: [issue] });
    }
    return [...groups.entries()]
      .sort((a, b) => groupOrder(a[0] as Parameters<typeof groupOrder>[0]) - groupOrder(b[0] as Parameters<typeof groupOrder>[0]))
      .map(([, value]) => value);
  }, [issues]);
  const topIssues = useMemo(() => issues.filter((item) => item.severity === 'error').concat(issues.filter((item) => item.severity !== 'error')).slice(0, 3), [issues]);

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
              <SummaryCard label="Likely stale sessions" value={String(data.stale_session_count ?? operationalSummary.stale_session_count ?? 0)} tone={Number(data.stale_session_count ?? operationalSummary.stale_session_count ?? 0) > 0 ? 'bad' : 'good'} />
              <SummaryCard label="Incomplete questionnaire sessions" value={String(operationalSummary.incomplete_questionnaire_count ?? 0)} tone={Number(operationalSummary.incomplete_questionnaire_count ?? 0) > 0 ? 'warn' : 'good'} />
              <SummaryCard label="Lifecycle anomalies" value={String(operationalSummary.lifecycle_anomaly_count ?? 0)} tone={Number(operationalSummary.lifecycle_anomaly_count ?? 0) > 0 ? 'bad' : 'good'} />
              <SummaryCard label={t('diagnostics.warningCount')} value={String(issues.length)} tone={issues.length > 0 ? 'bad' : 'good'} />
            </div>
          </section>
          <section className="panel">
            <h3>{t('diagnostics.warnings')}</h3>
            {issues.length === 0 ? <StatusBadge label={t('diagnostics.noWarnings')} tone="good" /> : null}
            {topIssues.length > 0 ? (
              <article className="info-card info-card--bad">
                <h4>Most important issues first</h4>
                <ul>
                  {topIssues.map((issue) => (
                    <li key={issue.id}>{issue.detail}</li>
                  ))}
                </ul>
              </article>
            ) : null}
            {groupedIssues.length > 0 ? (
              <div className="stack-grid">
                {groupedIssues.map((group, groupIndex) => (
                  <article
                    key={`${group.label}-${groupIndex}`}
                    className={`info-card ${group.items.some((item) => item.severity === 'error') ? 'info-card--bad' : 'info-card--warn'}`}
                  >
                    <h4>{group.label}</h4>
                    <ul>
                      {group.items.map((issue) => (
                        <li key={issue.id}>{issue.detail}</li>
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
