import React, { useEffect, useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { downloadRunExportArtifact, getRunExports, listRuns } from '../lib/api';

function downloadBlob(filename: string, blob: Blob) {
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
  const [downloading, setDownloading] = useState('');
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

  const artifacts = Array.isArray(data?.artifacts) ? (data?.artifacts as Array<Record<string, unknown>>) : [];

  async function downloadArtifact(artifactType: string, filename: string) {
    if (!runId) return;
    setDownloading(artifactType);
    try {
      const blob = await downloadRunExportArtifact(runId, artifactType);
      downloadBlob(filename, blob);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setDownloading('');
    }
  }

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
          <p>generated_at: {String(data.generated_at ?? 'n/a')}</p>
          <p>{String(data.message ?? '')}</p>
          <pre>available_outputs: {JSON.stringify(data.available_outputs ?? {}, null, 2)}</pre>
          {String(data.export_state) === 'empty' ? <p>No sessions yet for this run, so exports are not available.</p> : null}
          {artifacts.length > 0 ? (
            <ul>
              {artifacts.map((artifact) => (
                <li key={String(artifact.artifact_type)}>
                  {String(artifact.artifact_type)} · {String(artifact.category)} · {String(artifact.size_bytes)} bytes ·{' '}
                  {String(artifact.available) === 'true' ? 'available' : 'empty'}{' '}
                  <button
                    onClick={() => downloadArtifact(String(artifact.artifact_type), String(artifact.filename))}
                    disabled={downloading === String(artifact.artifact_type)}
                  >
                    {downloading === String(artifact.artifact_type) ? 'Downloading...' : 'Download'}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {String(data.export_state) === 'available' && artifacts.length === 0 ? <p>Run has sessions but no export artifacts were generated.</p> : null}
          {Array.isArray(data?.warnings) && (data?.warnings as unknown[]).length > 0 ? (
            <p>
              warnings ({(data?.warnings as unknown[]).length}){' '}
              <button onClick={() => downloadBlob(`${String(data.run_id)}_export_warnings.json`, new Blob([JSON.stringify(data?.warnings ?? [], null, 2)]))}>
                Download
              </button>
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
