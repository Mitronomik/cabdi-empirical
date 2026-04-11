import React, { useEffect, useMemo, useState } from 'react';

import { KbdMono, StatusBadge, SummaryCard } from '../components/OperatorPrimitives';
import type { MessageKey } from '../i18n/messages';
import { localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { getDashboard } from '../lib/api';

function blockerTone(severity: string): 'bad' | 'warn' {
  return severity === 'error' ? 'bad' : 'warn';
}

type DashboardAction = {
  action: 'inspect_run' | 'activate_run' | 'monitor_sessions' | 'open_diagnostics' | 'download_exports';
  page: 'run' | 'sessions' | 'diagnostics' | 'exports';
  target_run_id: string;
};

const dashboardActionKeyMap: Record<DashboardAction['action'], MessageKey> = {
  inspect_run: 'dashboard.action.inspectRun',
  activate_run: 'dashboard.action.activateRun',
  monitor_sessions: 'dashboard.action.monitorSessions',
  open_diagnostics: 'dashboard.action.openDiagnostics',
  download_exports: 'dashboard.action.downloadExports',
};
const MAX_VISIBLE_BLOCKERS = 8;

export function DashboardPage({
  onNavigate,
}: {
  onNavigate: (page: 'run' | 'sessions' | 'diagnostics' | 'exports', targetRunId?: string) => void;
}) {
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
  const focusOperationalSummary = ((focusRun?.operational_summary as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const focusWarnings = (Array.isArray(focusRun?.warnings) ? focusRun?.warnings : []) as string[];
  const blockers = (dashboard?.blockers as Array<Record<string, unknown>> | undefined) ?? [];
  const visibleBlockers = blockers.slice(0, MAX_VISIBLE_BLOCKERS);
  const nextActions = useMemo(
    () => (((dashboard?.next_actions as DashboardAction[] | undefined) ?? (focusRun?.next_actions as DashboardAction[] | undefined) ?? []) as DashboardAction[]),
    [dashboard?.next_actions, focusRun?.next_actions],
  );
  const focusRunId = String(focusRun?.run_id ?? '');
  const localizeActionLabel = (action: DashboardAction): string => {
    return t(dashboardActionKeyMap[action.action]);
  };

  return (
    <section>
      <h2>{t('dashboard.title')}</h2>
      <p className="muted">{t('dashboard.description')}</p>

      <section className="panel toolbar">
        <p>
          {t('dashboard.focusRun')}: {focusRunId ? <KbdMono>{focusRunId}</KbdMono> : t('common.na')}
        </p>
        <button className="secondary-btn" onClick={load} disabled={loading}>
          {loading ? t('common.loading') : t('dashboard.refresh')}
        </button>
      </section>

      {error ? (
        <p role="alert" className="alert-error">
          {error}
        </p>
      ) : null}

      <section className="panel">
        <h3>{t('dashboard.globalSnapshotTitle')}</h3>
        <div className="summary-grid">
          <SummaryCard label={t('dashboard.global.totalRuns')} value={String(runCounts.total ?? 0)} tone="info" />
          <SummaryCard label={t('dashboard.global.activeRuns')} value={String(runCounts.active ?? 0)} tone="good" />
          <SummaryCard label={t('dashboard.global.draftOrPausedRuns')} value={String(Number(runCounts.draft ?? 0) + Number(runCounts.paused ?? 0))} tone={Number(runCounts.draft ?? 0) + Number(runCounts.paused ?? 0) > 0 ? 'warn' : 'good'} />
          <SummaryCard label={t('dashboard.global.launchBlockers')} value={String(blockers.length)} tone={blockers.length > 0 ? 'bad' : 'good'} />
          <SummaryCard label={t('dashboard.global.sessionsAllRuns')} value={String(globalSessionCounts.total ?? 0)} tone="info" />
          <SummaryCard label={t('dashboard.global.inProgress')} value={String(globalSessionCounts.in_progress ?? 0)} tone="warn" />
          <SummaryCard label={t('dashboard.global.awaitingFinalSubmit')} value={String(globalSessionCounts.awaiting_final_submit ?? 0)} tone={Number(globalSessionCounts.awaiting_final_submit ?? 0) > 0 ? 'warn' : 'good'} />
          <SummaryCard label={t('dashboard.global.finalized')} value={String(globalSessionCounts.finalized ?? 0)} tone="good" />
        </div>
      </section>

      {focusRun ? (
        <section className="panel">
          <h3>{t('dashboard.focusSnapshotTitle')}</h3>
          <div className="summary-grid">
            <SummaryCard label={t('dashboard.focus.runStatus')} value={localizeStatus(t, focusRun.status)} tone="info" />
            <SummaryCard label={t('dashboard.focus.launchable')} value={String(Boolean(focusRun.launchable))} tone={focusRun.launchable ? 'good' : 'bad'} />
            <SummaryCard label={t('dashboard.focus.activeSessions')} value={String(Number(focusCounts.in_progress ?? 0) + Number(focusCounts.paused ?? 0))} tone="warn" />
            <SummaryCard label={t('dashboard.focus.awaitingFinalSubmit')} value={String(focusCounts.awaiting_final_submit ?? 0)} tone={Number(focusCounts.awaiting_final_submit ?? 0) > 0 ? 'warn' : 'good'} />
            <SummaryCard label={t('dashboard.focus.likelyStaleSessions')} value={String(focusRun.stale_session_count ?? focusOperationalSummary.stale_session_count ?? 0)} tone={Number(focusRun.stale_session_count ?? focusOperationalSummary.stale_session_count ?? 0) > 0 ? 'bad' : 'good'} />
            <SummaryCard
              label={t('dashboard.focus.exportsAvailable')}
              value={String((focusRun.export_availability as Record<string, unknown> | undefined)?.available_artifact_count ?? 0)}
              tone={Number((focusRun.export_availability as Record<string, unknown> | undefined)?.available_artifact_count ?? 0) > 0 ? 'good' : 'warn'}
            />
          </div>
          <p className="muted">{t('dashboard.focus.publicSlug')}: {String(focusRun.public_slug ?? t('common.na'))}</p>
          <p className="muted">{t('dashboard.focus.launchabilityReason')}: {String(focusRun.launchability_reason ?? t('common.na'))}</p>
        </section>
      ) : null}

      <section className="panel">
        <h3>{t('dashboard.blockersTitle')}</h3>
        {visibleBlockers.length === 0 ? <StatusBadge label={t('dashboard.blockersEmpty')} tone="good" /> : null}
        {visibleBlockers.length > 0 ? (
          <div className="stack-grid">
            {visibleBlockers.map((blocker, index) => (
              <article key={`${String(blocker.run_id)}-${index}`} className={`info-card ${blockerTone(String(blocker.severity ?? 'warning')) === 'bad' ? 'info-card--bad' : 'info-card--warn'}`}>
                <h4>{String(blocker.run_id)}</h4>
                <p>
                  <StatusBadge label={localizeStatus(t, blocker.run_status)} tone={blockerTone(String(blocker.severity ?? 'warning'))} />
                </p>
                <p className="muted">{String(blocker.reason ?? t('dashboard.blockerReasonFallback'))}</p>
                <p>
                  {t('dashboard.focus.publicSlug')}: <KbdMono>{String(blocker.public_slug ?? t('common.na'))}</KbdMono>
                </p>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel">
        <h3>{t('dashboard.warningsTitle')}</h3>
        {focusWarnings.length === 0 ? <StatusBadge label={t('dashboard.warningsEmpty')} tone="good" /> : null}
        {focusWarnings.length > 0 ? (
          <ul>
            {focusWarnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="panel">
        <h3>{t('dashboard.nextActionsTitle')}</h3>
        <div className="toolbar">
          {nextActions.map((action) => (
            <button
              key={`${action.action}-${action.target_run_id}`}
              className={action.action === 'activate_run' ? 'primary-btn' : 'secondary-btn'}
              onClick={() => onNavigate(action.page, action.target_run_id)}
              data-target-run-id={action.target_run_id}
              title={`${t('dashboard.nextActionTargetRun')}: ${action.target_run_id}`}
            >
              {localizeActionLabel(action)} ({action.target_run_id})
            </button>
          ))}
        </div>
      </section>
    </section>
  );
}
