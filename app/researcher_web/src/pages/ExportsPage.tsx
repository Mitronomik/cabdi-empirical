import React, { useEffect, useMemo, useState } from 'react';

import { KbdMono, StatusBadge, SummaryCard } from '../components/OperatorPrimitives';
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
  const availableCount = artifacts.filter((item) => Boolean(item.available)).length;
  const selectedRun = useMemo(() => runs.find((run) => run.run_id === runId), [runId, runs]);
  const exportState = String(data?.export_state ?? 'unknown');

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
      <p className="muted">{t('exports.workflowHint')}</p>
      <section className="panel">
        <div className="toolbar">
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
          <button className="primary-btn" onClick={load} disabled={loadingExports || !runId}>
            {loadingExports ? t('common.loading') : t('exports.load')}
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
            <h3>{t('exports.summaryTitle')}</h3>
            <div className="summary-grid">
              <SummaryCard label={t('exports.state')} value={localizeStatus(t, data.export_state ?? 'unknown')} tone="info" />
              <SummaryCard label={t('exports.summaryArtifacts')} value={String(artifacts.length)} tone="info" />
              <SummaryCard label={t('exports.summaryAvailable')} value={String(availableCount)} tone={availableCount > 0 ? 'good' : 'warn'} />
              <SummaryCard label={t('exports.generatedAt')} value={String(data.generated_at ?? t('common.na'))} />
            </div>
            <p>{String(data.message ?? '')}</p>
            {exportState === 'empty' ? <p className="state-banner state-banner--empty">{t('exports.empty')}</p> : null}
            {exportState === 'available' && artifacts.length === 0 ? <p className="state-banner state-banner--warn">{t('exports.noArtifacts')}</p> : null}
            {exportState === 'available' && artifacts.length > 0 ? (
              <p className="state-banner state-banner--good">Exports are generated and available for download below.</p>
            ) : null}
            {exportState !== 'available' && exportState !== 'empty' ? (
              <p className="state-banner state-banner--warn">Exports are not generated yet for this run.</p>
            ) : null}
          </section>

          {artifacts.length > 0 ? (
            <section className="panel">
              <h3>{t('exports.artifactsTitle')}</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t('exports.tableType')}</th>
                      <th>{t('exports.tableCategory')}</th>
                      <th>{t('exports.artifactSize')}</th>
                      <th>{t('exports.artifactAvailable')}</th>
                      <th>{t('run.tableActions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {artifacts.map((artifact) => {
                      const artifactType = String(artifact.artifact_type);
                      return (
                        <tr key={artifactType}>
                          <td>{artifactType}</td>
                          <td>{String(artifact.category)}</td>
                          <td>{String(artifact.size_bytes)} {t('exports.bytes')}</td>
                          <td>
                            <StatusBadge label={localizeStatus(t, String(artifact.available) === 'true' ? 'available' : 'empty')} tone={artifact.available ? 'good' : 'warn'} />
                          </td>
                          <td>
                            <button
                              className="primary-btn"
                              onClick={() => downloadArtifact(artifactType, String(artifact.filename))}
                              disabled={downloading === artifactType || !artifact.available}
                            >
                              {downloading === artifactType ? t('exports.downloading') : t('exports.download')}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </>
      ) : (
        <p>{t('exports.notLoaded')}</p>
      )}
    </section>
  );
}
