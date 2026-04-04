import React, { useEffect, useMemo, useState } from 'react';

import { KbdMono, StatusBadge, SummaryCard } from '../components/OperatorPrimitives';
import { formatProgress, localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { getRunSessions, listRuns } from '../lib/api';
import { parseRunSummary, pickDefaultRunId, runOptionLabelLocalized } from '../lib/researcherUi';

function sessionTone(status: string): 'good' | 'warn' | 'bad' | 'neutral' {
  if (status === 'completed' || status === 'finalized') return 'good';
  if (status === 'in_progress' || status === 'awaiting_final_submit') return 'warn';
  return 'neutral';
}

export function SessionMonitorPage() {
  const [runId, setRunId] = useState('');
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [runs, setRuns] = useState<Array<ReturnType<typeof parseRunSummary>>>([]);
  const [error, setError] = useState('');
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
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
    setLoadingSessions(true);
    try {
      const out = await getRunSessions(runId);
      setData(out);
      setError('');
    } catch (err) {
      setError(localizeOperatorError(t, err));
    } finally {
      setLoadingSessions(false);
    }
  }

  const sessions = (data?.sessions as Array<Record<string, unknown>> | undefined) ?? [];
  const counts = (data?.counts as Record<string, number> | undefined) ?? {};
  const selectedRun = useMemo(() => runs.find((run) => run.run_id === runId), [runId, runs]);

  return (
    <section>
      <h2>{t('sessions.title')}</h2>
      <p className="muted">{t('sessions.workflowHint')}</p>

      <section className="panel">
        <div className="toolbar">
          {loadingRuns ? <p>{t('common.loadingRuns')}</p> : null}
          {runs.length === 0 && !loadingRuns ? <p>{t('common.noRuns')}</p> : null}
          <select value={runId} onChange={(e) => setRunId(e.target.value)}>
            <option value="">{t('sessions.runId')}</option>
            {runs.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {runOptionLabelLocalized(run, (value) => localizeStatus(t, value))}
              </option>
            ))}
          </select>
          <button className="primary-btn" onClick={load} disabled={loadingSessions || !runId}>
            {loadingSessions ? t('common.loading') : t('sessions.load')}
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
            <h3>{t('sessions.summaryTitle')}</h3>
            <div className="summary-grid">
              <SummaryCard label={t('sessions.runStatus')} value={localizeStatus(t, data.run_status ?? 'unknown')} tone="info" />
              <SummaryCard label={t('sessions.summaryTotal')} value={String(sessions.length)} tone="info" />
              <SummaryCard label={t('sessions.summaryInProgress')} value={String(counts.in_progress ?? 0)} tone="warn" />
              <SummaryCard label={t('sessions.summaryCompleted')} value={String((counts.completed ?? 0) + (counts.finalized ?? 0))} tone="good" />
            </div>
          </section>

          <section className="panel">
            <h3>{t('sessions.counts')}</h3>
            <div className="toolbar">
              {Object.entries(counts).map(([key, value]) => (
                <StatusBadge key={key} label={`${localizeStatus(t, key)}: ${value}`} tone={sessionTone(key)} />
              ))}
            </div>
          </section>

          <section className="panel">
            <h3>{t('sessions.tableTitle')}</h3>
            {sessions.length === 0 ? <p>{t('sessions.empty')}</p> : null}
            {sessions.length > 0 ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t('sessions.tableParticipant')}</th>
                      <th>{t('sessions.tableStatus')}</th>
                      <th>{t('sessions.tableProgress')}</th>
                      <th>{t('sessions.tableLastActivity')}</th>
                      <th>{t('sessions.tableStarted')}</th>
                      <th>{t('sessions.tableCompleted')}</th>
                      <th>{t('sessions.tableSessionId')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map((session) => (
                      <tr key={String(session.session_id)}>
                        <td>{String(session.participant_id)}</td>
                        <td>
                          <StatusBadge label={localizeStatus(t, session.status)} tone={sessionTone(String(session.status ?? 'unknown'))} />
                        </td>
                        <td>{formatProgress(t, session.current_block_index ?? 0, session.current_trial_index ?? 0)}</td>
                        <td>{String(session.last_activity_at ?? t('common.na'))}</td>
                        <td>{String(session.started_at ?? t('common.na'))}</td>
                        <td>{String(session.completed_at ?? t('common.na'))}</td>
                        <td>
                          <KbdMono>{String(session.session_id)}</KbdMono>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>
        </>
      ) : (
        <p>{t('sessions.notLoaded')}</p>
      )}
    </section>
  );
}
