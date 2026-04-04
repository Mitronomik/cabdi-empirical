import React, { useEffect, useMemo, useState } from 'react';

import { formatProgress, localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { getRunSessions, listRuns } from '../lib/api';
import { parseRunSummary, pickDefaultRunId, runOptionLabelLocalized } from '../lib/researcherUi';

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
  const selectedRun = useMemo(() => runs.find((run) => run.run_id === runId), [runId, runs]);

  return (
    <section>
      <h2>{t('sessions.title')}</h2>
      <p>{t('sessions.workflowHint')}</p>
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
      <button onClick={load} disabled={loadingSessions || !runId}>
        {loadingSessions ? t('common.loading') : t('sessions.load')}
      </button>
      {selectedRun ? <p>{t('common.selectedRun')}: {runOptionLabelLocalized(selectedRun, (value) => localizeStatus(t, value))} · {selectedRun.run_id}</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {data ? (
        <>
          <p>{t('sessions.runStatus')}: {localizeStatus(t, data.run_status ?? 'unknown')}</p>
          <pre>{t('sessions.counts')}: {JSON.stringify(data.counts ?? {}, null, 2)}</pre>
          {sessions.length === 0 ? <p>{t('sessions.empty')}</p> : null}
          {sessions.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>{t('sessions.tableParticipant')}</th>
                  <th>{t('sessions.tableStatus')}</th>
                  <th>{t('sessions.tableStarted')}</th>
                  <th>{t('sessions.tableLastActivity')}</th>
                  <th>{t('sessions.tableCompleted')}</th>
                  <th>{t('sessions.tableProgress')}</th>
                  <th>{t('sessions.tableSessionId')}</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={String(session.session_id)}>
                    <td>{String(session.participant_id)}</td>
                    <td>{localizeStatus(t, session.status)}</td>
                    <td>{String(session.started_at ?? t('common.na'))}</td>
                    <td>{String(session.last_activity_at ?? t('common.na'))}</td>
                    <td>{String(session.completed_at ?? t('common.na'))}</td>
                    <td>
                      {formatProgress(t, session.current_block_index ?? 0, session.current_trial_index ?? 0)}
                    </td>
                    <td>{String(session.session_id)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </>
      ) : (
        <p>{t('sessions.notLoaded')}</p>
      )}
    </section>
  );
}
