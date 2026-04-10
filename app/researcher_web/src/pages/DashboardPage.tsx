import React, { useEffect, useMemo, useState } from 'react';

import { KbdMono, StatusBadge, SummaryCard } from '../components/OperatorPrimitives';
import { localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { getDashboard } from '../lib/api';

function blockerTone(severity: string): 'bad' | 'warn' {
  return severity === 'error' ? 'bad' : 'warn';
}

type DashboardAction = {
  action: string;
  label: string;
  page: 'run' | 'sessions' | 'diagnostics' | 'exports';
  target_run_id: string;
};

export function DashboardPage({ onNavigate }: { onNavigate: (page: 'run' | 'sessions' | 'diagnostics' | 'exports') => void }) {
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { t } = useLocale();

  async function load() {
    setLoading(true);
    setError('');
    try {
      const payload = await getDashboard();
      setDashboard(payload);
    } catch (err) {
      setError(localizeOperatorError(t, err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const globalSnapshot = (dashboard?.global_snapshot as Record<string, unknown> | undefined) ?? {};
  const runCounts = (globalSnapshot.run_counts as Record<string, unknown> | undefined) ?? {};
  const globalSessionCounts = (globalSnapshot.session_counts as Record<string, unknown> | undefined) ?? {};

  const focusRun = (dashboard?.focus_run_snapshot as Record<string, unknown> | undefined) ?? null;
  const focusCounts = ((focusRun?.counts as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const focusWarnings = (Array.isArray(focusRun?.warnings) ? focusRun?.warnings : []) as string[];
  const blockers = ((dashboard?.blockers as Array<Record<string, unknown>> | undefined) ?? []).slice(0, 8);
  const nextActions = useMemo(
    () => (((dashboard?.next_actions as DashboardAction[] | undefined) ?? (focusRun?.next_actions as DashboardAction[] | undefined) ?? []) as DashboardAction[]),
    [dashboard?.next_actions, focusRun?.next_actions],
  );
  const focusRunId = String(focusRun?.run_id ?? '');

  return (
    <section>
      <h2>Prelaunch Readiness Center</h2>
      <p className="muted">Canonical backend dashboard snapshot with separated global and focus-run truths.</p>

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
        <h3>Global operational snapshot</h3>
        <div className="summary-grid">
          <SummaryCard label="Total runs" value={String(runCounts.total ?? 0)} tone="info" />
          <SummaryCard label="Active runs" value={String(runCounts.active ?? 0)} tone="good" />
          <SummaryCard label="Draft or paused runs" value={String(Number(runCounts.draft ?? 0) + Number(runCounts.paused ?? 0))} tone={Number(runCounts.draft ?? 0) + Number(runCounts.paused ?? 0) > 0 ? 'warn' : 'good'} />
          <SummaryCard label="Launch blockers" value={String(blockers.length)} tone={blockers.length > 0 ? 'bad' : 'good'} />
          <SummaryCard label="Sessions (all runs)" value={String(globalSessionCounts.total ?? 0)} tone="info" />
          <SummaryCard label="In progress" value={String(globalSessionCounts.in_progress ?? 0)} tone="warn" />
          <SummaryCard label="Awaiting final submit" value={String(globalSessionCounts.awaiting_final_submit ?? 0)} tone={Number(globalSessionCounts.awaiting_final_submit ?? 0) > 0 ? 'warn' : 'good'} />
          <SummaryCard label="Finalized" value={String(globalSessionCounts.finalized ?? 0)} tone="good" />
        </div>
      </section>

      {focusRun ? (
        <section className="panel">
          <h3>Focus run snapshot</h3>
          <div className="summary-grid">
            <SummaryCard label="Run status" value={localizeStatus(t, focusRun.status)} tone="info" />
            <SummaryCard label="Launchable" value={String(Boolean(focusRun.launchable))} tone={focusRun.launchable ? 'good' : 'bad'} />
            <SummaryCard label="Active sessions" value={String(Number(focusCounts.in_progress ?? 0) + Number(focusCounts.paused ?? 0))} tone="warn" />
            <SummaryCard label="Awaiting final submit" value={String(focusCounts.awaiting_final_submit ?? 0)} tone={Number(focusCounts.awaiting_final_submit ?? 0) > 0 ? 'warn' : 'good'} />
            <SummaryCard label="Likely stale sessions" value={String(focusRun.stale_session_count ?? 0)} tone={Number(focusRun.stale_session_count ?? 0) > 0 ? 'bad' : 'good'} />
            <SummaryCard
              label="Exports available"
              value={String((focusRun.export_availability as Record<string, unknown> | undefined)?.available_artifact_count ?? 0)}
              tone={Number((focusRun.export_availability as Record<string, unknown> | undefined)?.available_artifact_count ?? 0) > 0 ? 'good' : 'warn'}
            />
          </div>
          <p className="muted">Public slug: {String(focusRun.public_slug ?? t('common.na'))}</p>
          <p className="muted">Launchability reason: {String(focusRun.launchability_reason ?? t('common.na'))}</p>
        </section>
      ) : null}

      <section className="panel">
        <h3>Launch blockers</h3>
        {blockers.length === 0 ? <StatusBadge label="No launch blockers detected." tone="good" /> : null}
        {blockers.length > 0 ? (
          <div className="stack-grid">
            {blockers.map((blocker, index) => (
              <article key={`${String(blocker.run_id)}-${index}`} className={`info-card ${blockerTone(String(blocker.severity ?? 'warning')) === 'bad' ? 'info-card--bad' : 'info-card--warn'}`}>
                <h4>{String(blocker.run_id)}</h4>
                <p>
                  <StatusBadge label={localizeStatus(t, blocker.run_status)} tone={blockerTone(String(blocker.severity ?? 'warning'))} />
                </p>
                <p className="muted">{String(blocker.reason ?? 'No launchability reason available.')}</p>
                <p>
                  Public slug: <KbdMono>{String(blocker.public_slug ?? t('common.na'))}</KbdMono>
                </p>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel">
        <h3>Top diagnostics / warnings</h3>
        {focusWarnings.length === 0 ? <StatusBadge label="No warning flags in the loaded focus run." tone="good" /> : null}
        {focusWarnings.length > 0 ? (
          <ul>
            {focusWarnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="panel">
        <h3>Next actions</h3>
        <div className="toolbar">
          {nextActions.map((action) => (
            <button
              key={`${action.action}-${action.target_run_id}`}
              className={action.action === 'activate_run' ? 'primary-btn' : 'secondary-btn'}
              onClick={() => onNavigate(action.page)}
              data-target-run-id={action.target_run_id}
              title={`Target run: ${action.target_run_id}`}
            >
              {action.label} ({action.target_run_id})
            </button>
          ))}
        </div>
      </section>
    </section>
  );
}
