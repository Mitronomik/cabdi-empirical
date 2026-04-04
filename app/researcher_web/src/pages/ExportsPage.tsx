import React, { useEffect, useMemo, useState } from 'react';

import { localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { downloadRunExportArtifact, getRunExports, listRuns } from '../lib/api';
import { parseRunSummary, pickDefaultRunId, runOptionLabelLocalized } from '../lib/researcherUi';

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
  const [runs, setRuns] = useState<Array<ReturnType<typeof parseRunSummary>>>([]);
  const [error, setError] = useState('');
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingExports, setLoadingExports] = useState(false);
  const [downloading, setDownloading] = useState('');
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
    setLoadingExports(true);
    try {
      const out = await getRunExports(runId);
      setData(out);
      setError('');
    } catch (err) {
      setError(localizeOperatorError(t, err));
    } finally {
      setLoadingExports(false);
    }
  }

  const artifacts = Array.isArray(data?.artifacts) ? (data?.artifacts as Array<Record<string, unknown>>) : [];
  const selectedRun = useMemo(() => runs.find((run) => run.run_id === runId), [runId, runs]);

  async function downloadArtifact(artifactType: string, filename: string) {
    if (!runId) return;
    setDownloading(artifactType);
    try {
      const blob = await downloadRunExportArtifact(runId, artifactType);
      downloadBlob(filename, blob);
    } catch (err) {
      setError(localizeOperatorError(t, err));
    } finally {
      setDownloading('');
    }
  }

  return (
    <section>
      <h2>{t('exports.title')}</h2>
      <p>{t('exports.workflowHint')}</p>
      {loadingRuns ? <p>{t('common.loadingRuns')}</p> : null}
      {runs.length === 0 && !loadingRuns ? <p>{t('common.noRuns')}</p> : null}
      <select value={runId} onChange={(e) => setRunId(e.target.value)}>
        <option value="">{t('exports.runId')}</option>
        {runs.map((run) => (
          <option key={run.run_id} value={run.run_id}>
            {runOptionLabelLocalized(run, (value) => localizeStatus(t, value))}
          </option>
        ))}
      </select>
      <button onClick={load} disabled={loadingExports || !runId}>
        {loadingExports ? t('common.loading') : t('exports.load')}
      </button>
      {selectedRun ? <p>{t('common.selectedRun')}: {runOptionLabelLocalized(selectedRun, (value) => localizeStatus(t, value))} · {selectedRun.run_id}</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {data ? (
        <>
          <p>{t('exports.state')}: {localizeStatus(t, data.export_state ?? 'unknown')}</p>
          <p>{t('exports.generatedAt')}: {String(data.generated_at ?? t('common.na'))}</p>
          <p>{String(data.message ?? '')}</p>
          {String(data.export_state) === 'empty' ? <p>{t('exports.empty')}</p> : null}
          {artifacts.length > 0 ? (
            <ul>
              {artifacts.map((artifact) => (
                <li key={String(artifact.artifact_type)}>
                  {String(artifact.artifact_type)} · {String(artifact.category)} · {t('exports.artifactSize')}: {String(artifact.size_bytes)} {t('exports.bytes')} ·{' '}
                  {t('exports.artifactAvailable')}: {localizeStatus(t, String(artifact.available) === 'true' ? 'available' : 'empty')}{' '}
                  <button
                    onClick={() => downloadArtifact(String(artifact.artifact_type), String(artifact.filename))}
                    disabled={downloading === String(artifact.artifact_type)}
                  >
                    {downloading === String(artifact.artifact_type) ? t('exports.downloading') : t('exports.download')}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {String(data.export_state) === 'available' && artifacts.length === 0 ? <p>{t('exports.noArtifacts')}</p> : null}
        </>
      ) : (
        <p>{t('exports.notLoaded')}</p>
      )}
    </section>
  );
}
