import React, { useEffect, useMemo, useState } from 'react';

import { KbdMono, StatusBadge, SummaryCard } from '../components/OperatorPrimitives';
import { localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { getRunDiagnostics, getRunExports, getRunSessions, listRuns } from '../lib/api';
import { parseRunSummary, type RunSummary } from '../lib/researcherUi';

function blockerTone(run: RunSummary): 'bad' | 'warn' {
  if (run.status === 'draft') return 'bad';
  return 'warn';
}

export function DashboardPage({ onNavigate }: { onNavigate: (page: 'run' | 'sessions' | 'diagnostics' | 'exports') => void }) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [focusRunId, setFocusRunId] = useState('');
  const [sessionsData, setSessionsData] = useState<Record<string, unknown> | null>(null);
  const [diagnosticsData, setDiagnosticsData] = useState<Record<string, unknown> | null>(null);
  const [exportsData, setExportsData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { t } = useLocale();

  async function load() {
    setLoading(true);
    setError('');
    try {
      const parsedRuns = (await listRuns()).slice(0, 30).map(parseRunSummary);
      setRuns(parsedRuns);

      const activeRun = parsedRuns.find((run) => run.status === 'active');
      const nextFocusRunId = activeRun?.run_id ?? parsedRuns[0]?.run_id ?? '';
      setFocusRunId(nextFocusRunId);

      if (!nextFocusRunId) {
        setSessionsData(null);
        setDiagnosticsData(null);
        setExportsData(null);
        return;
      }

      const [sessionsResult, diagnosticsResult, exportsResult] = await Promise.allSettled([
        getRunSessions(nextFocusRunId),
        getRunDiagnostics(nextFocusRunId),
        getRunExports(nextFocusRunId),
      ]);

      setSessionsData(sessionsResult.status === 'fulfilled' ? sessionsResult.value : null);
      setDiagnosticsData(diagnosticsResult.status === 'fulfilled' ? diagnosticsResult.value : null);
      setExportsData(exportsResult.status === 'fulfilled' ? exportsResult.value : null);

      if (sessionsResult.status === 'rejected' || diagnosticsResult.status === 'rejected' || exportsResult.status === 'rejected') {
        setError('Some dashboard sections could not be loaded. Open detailed pages for complete diagnostics.');
      }
    } catch (err) {
      setError(localizeOperatorError(t, err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const activeRuns = useMemo(() => runs.filter((run) => run.status === 'active'), [runs]);
  const draftOrPausedRuns = useMemo(() => runs.filter((run) => run.status === 'draft' || run.status === 'paused'), [runs]);
  const blockers = useMemo(
    () => runs.filter((run) => !run.launchable || run.launchability_state !== 'launchable' || run.status === 'draft'),
    [runs],
  );

  const counts = ((sessionsData?.counts as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const sessions = (sessionsData?.sessions as Array<Record<string, unknown>> | undefined) ?? [];
  const activeSessionCount = Number(counts.in_progress ?? 0) + Number(counts.paused ?? 0);
  const awaitingFinalSubmitCount = Number(counts.awaiting_final_submit ?? 0);
  const finalizedCount = Number(counts.finalized ?? 0);

  const staleSessionLikelyCount = useMemo(() => {
    const thresholdMs = 30 * 60 * 1000;
    const now = Date.now();
    return sessions.filter((session) => {
      const status = String(session.status ?? '');
      if (status === 'completed' || status === 'finalized') return false;
      const raw = session.last_activity_at ?? session.started_at;
      if (!raw) return false;
      const ts = Date.parse(String(raw));
      if (Number.isNaN(ts)) return false;
      return now - ts > thresholdMs;
    }).length;
  }, [sessions]);

  const warnings = useMemo(() => {
    const diagnosticWarnings = Array.isArray(diagnosticsData?.warnings)
      ? diagnosticsData.warnings.map((item) => String(item))
      : [];
    if (staleSessionLikelyCount > 0) {
      diagnosticWarnings.unshift(`Potential stale sessions: ${staleSessionLikelyCount}`);
    }
    return diagnosticWarnings.slice(0, 5);
  }, [diagnosticsData?.warnings, staleSessionLikelyCount]);

  const artifacts = Array.isArray(exportsData?.artifacts) ? (exportsData.artifacts as Array<Record<string, unknown>>) : [];
  const availableExportCount = artifacts.filter((artifact) => Boolean(artifact.available)).length;

  return (
    <section>
      <h2>Prelaunch Readiness Center</h2>
      <p className="muted">Single-screen operational view for launchability, active work, blockers, and next actions.</p>

      <section className="panel toolbar">
        <p>
          Focus run: {focusRunId ? <KbdMono>{focusRunId}</KbdMono> : t('common.na')}
        </p>
        <button className="secondary-btn" onClick={load} disabled={loading}>
          {loading ? t('common.loading') : 'Refresh dashboard'}
        </button>
      </section>

      {error ? (
        <p role="alert" className="alert-error">
          {error}
        </p>
      ) : null}

      <section className="panel">
        <h3>Operational snapshot</h3>
        <div className="summary-grid">
          <SummaryCard label="Active runs" value={String(activeRuns.length)} tone="good" />
          <SummaryCard label="Draft or paused runs" value={String(draftOrPausedRuns.length)} tone={draftOrPausedRuns.length > 0 ? 'warn' : 'good'} />
          <SummaryCard label="Launch blockers" value={String(blockers.length)} tone={blockers.length > 0 ? 'bad' : 'good'} />
          <SummaryCard label="Active sessions" value={String(activeSessionCount)} tone={activeSessionCount > 0 ? 'warn' : 'info'} />
          <SummaryCard label="Awaiting final submit" value={String(awaitingFinalSubmitCount)} tone={awaitingFinalSubmitCount > 0 ? 'warn' : 'good'} />
          <SummaryCard label="Finalized sessions" value={String(finalizedCount)} tone="good" />
          <SummaryCard label="Exports available" value={String(availableExportCount)} tone={availableExportCount > 0 ? 'good' : 'warn'} />
          <SummaryCard label="Top warnings" value={String(warnings.length)} tone={warnings.length > 0 ? 'bad' : 'good'} />
        </div>
      </section>

      <section className="panel">
        <h3>Launch blockers</h3>
        {blockers.length === 0 ? <StatusBadge label="No launch blockers detected." tone="good" /> : null}
        {blockers.length > 0 ? (
          <div className="stack-grid">
            {blockers.map((run) => (
              <article key={run.run_id} className={`info-card ${blockerTone(run) === 'bad' ? 'info-card--bad' : 'info-card--warn'}`}>
                <h4>{run.run_name || run.run_id}</h4>
                <p>
                  <StatusBadge label={localizeStatus(t, run.status)} tone={blockerTone(run)} />
                </p>
                <p className="muted">{run.launchability_reason || 'No launchability reason available.'}</p>
                <p>
                  Run ID: <KbdMono>{run.run_id}</KbdMono>
                </p>
                <button className="secondary-btn" onClick={() => onNavigate('run')}>
                  Inspect run
                </button>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel">
        <h3>Top diagnostics / warnings</h3>
        {warnings.length === 0 ? <StatusBadge label="No warning flags in the loaded focus run." tone="good" /> : null}
        {warnings.length > 0 ? (
          <ul>
            {warnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="panel">
        <h3>Next actions</h3>
        <div className="toolbar">
          <button className="primary-btn" onClick={() => onNavigate('run')}>
            Activate run
          </button>
          <button className="secondary-btn" onClick={() => onNavigate('run')}>
            Inspect run
          </button>
          <button className="secondary-btn" onClick={() => onNavigate('sessions')}>
            Monitor sessions
          </button>
          <button className="secondary-btn" onClick={() => onNavigate('diagnostics')}>
            Open diagnostics
          </button>
          <button className="secondary-btn" onClick={() => onNavigate('exports')}>
            Download exports
          </button>
        </div>
      </section>
    </section>
  );
}
