import React, { useEffect, useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { getRunSessions, listRuns } from '../lib/api';

export function SessionMonitorPage() {
  const [runId, setRunId] = useState('');
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [runs, setRuns] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState('');
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const { t } = useLocale();

  async function loadRuns() {
    setLoadingRuns(true);
    setError('');
    try {
      const items = await listRuns();
      setRuns(items.slice(0, 30));
      if (items.length > 0) setRunId((prev) => prev || String(items[0].run_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoadingRuns(false);
    }
  }

  useEffect(() => {
    void loadRuns();
  }, []);

  async function load() {
    if (!runId) {
      setError('Select a run first.');
      return;
    }
    setLoadingSessions(true);
    try {
      const out = await getRunSessions(runId);
      setData(out);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoadingSessions(false);
    }
  }

  const sessions = (data?.sessions as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <section>
      <h2>{t('sessions.title')}</h2>
      {loadingRuns ? <p>Loading runs...</p> : null}
      {runs.length === 0 && !loadingRuns ? <p>No runs found. Create and activate a run first.</p> : null}
      <select value={runId} onChange={(e) => setRunId(e.target.value)}>
        <option value="">{t('sessions.runId')}</option>
        {runs.map((run) => (
          <option key={String(run.run_id)} value={String(run.run_id)}>
            {String(run.run_name)} · {String(run.public_slug)} · {String(run.status)}
          </option>
        ))}
      </select>
      <button onClick={load} disabled={loadingSessions || !runId}>
        {loadingSessions ? 'Loading...' : t('sessions.load')}
      </button>
      {error ? <p role="alert">{error}</p> : null}
      {data ? (
        <>
          <p>run_id: {String(data.run_id)}</p>
          <p>public_slug: {String(data.public_slug ?? 'n/a')}</p>
          <p>run_status: {String(data.run_status ?? 'n/a')}</p>
          <pre>counts: {JSON.stringify(data.counts ?? {}, null, 2)}</pre>
          {sessions.length === 0 ? <p>No participant sessions found for this run yet.</p> : null}
          {sessions.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>session_id</th>
                  <th>run_id</th>
                  <th>participant_id</th>
                  <th>status</th>
                  <th>started_at</th>
                  <th>last_activity_at</th>
                  <th>completed_at</th>
                  <th>progress</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={String(session.session_id)}>
                    <td>{String(session.session_id)}</td>
                    <td>{String(session.run_id)}</td>
                    <td>{String(session.participant_id)}</td>
                    <td>{String(session.status)}</td>
                    <td>{String(session.started_at ?? 'n/a')}</td>
                    <td>{String(session.last_activity_at ?? 'n/a')}</td>
                    <td>{String(session.completed_at ?? 'n/a')}</td>
                    <td>
                      block {String(session.current_block_index ?? 0)} / trial {String(session.current_trial_index ?? 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
