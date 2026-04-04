import React, { useEffect, useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { getRunExports, listRuns } from '../lib/api';

function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function ExportsPage() {
  const [runId, setRunId] = useState('');
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [runs, setRuns] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState('');
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingExports, setLoadingExports] = useState(false);
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
    setLoadingExports(true);
    try {
      const out = await getRunExports(runId);
      setData(out);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoadingExports(false);
    }
  }

  const rawEventLog = String(data?.raw_event_log_jsonl ?? '');
  const trialSummaryCsv = String(data?.trial_summary_csv ?? '');
  const sessionSummaryCsv = String(data?.session_summary_csv ?? '');
  const analysisReadyCsv = String(data?.analysis_ready_csv ?? '');

  return (
    <section>
      <h2>{t('exports.title')}</h2>
      {loadingRuns ? <p>Loading runs...</p> : null}
      {runs.length === 0 && !loadingRuns ? <p>No runs found. Create and activate a run first.</p> : null}
      <select value={runId} onChange={(e) => setRunId(e.target.value)}>
        <option value="">{t('exports.runId')}</option>
        {runs.map((run) => (
          <option key={String(run.run_id)} value={String(run.run_id)}>
            {String(run.run_name)} · {String(run.public_slug)} · {String(run.status)}
          </option>
        ))}
      </select>
      <button onClick={load} disabled={loadingExports || !runId}>
        {loadingExports ? 'Loading...' : t('exports.load')}
      </button>
      {error ? <p role="alert">{error}</p> : null}
      {data ? (
        <>
          <p>run_id: {String(data.run_id)}</p>
          <p>export_state: {String(data.export_state ?? 'unknown')}</p>
          <p>{String(data.message ?? '')}</p>
          <pre>available_outputs: {JSON.stringify(data.available_outputs ?? {}, null, 2)}</pre>
          {String(data.export_state) === 'empty' ? <p>No sessions yet for this run, so exports are not available.</p> : null}
          {rawEventLog ? (
            <p>
              raw_event_log_jsonl ({rawEventLog.length} chars){' '}
              <button onClick={() => downloadText(`${String(data.run_id)}_raw_event_log.jsonl`, rawEventLog)}>Download</button>
            </p>
          ) : null}
          {trialSummaryCsv ? (
            <p>
              trial_summary_csv ({trialSummaryCsv.length} chars){' '}
              <button onClick={() => downloadText(`${String(data.run_id)}_trial_summary.csv`, trialSummaryCsv)}>Download</button>
            </p>
          ) : null}
          {sessionSummaryCsv ? (
            <p>
              session_summary_csv ({sessionSummaryCsv.length} chars){' '}
              <button onClick={() => downloadText(`${String(data.run_id)}_session_summary.csv`, sessionSummaryCsv)}>Download</button>
            </p>
          ) : null}
          {analysisReadyCsv ? (
            <p>
              analysis_ready_csv ({analysisReadyCsv.length} chars){' '}
              <button onClick={() => downloadText(`${String(data.run_id)}_analysis_ready.csv`, analysisReadyCsv)}>Download</button>
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
