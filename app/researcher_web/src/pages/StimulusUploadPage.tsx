import React, { useEffect, useMemo, useState } from 'react';

import { StatusBadge, SummaryCard, KbdMono } from '../components/OperatorPrimitives';
import { localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { listStimuli, uploadStimuli } from '../lib/api';
import { parseStimulusSetSummary } from '../lib/researcherUi';

function validationTone(status: string): 'good' | 'warn' | 'bad' | 'neutral' {
  if (status === 'valid') return 'good';
  if (status === 'warning_only') return 'warn';
  if (status === 'invalid') return 'bad';
  return 'neutral';
}

export function StimulusUploadPage() {
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [sets, setSets] = useState<Array<ReturnType<typeof parseStimulusSetSummary>>>([]);
  const { t } = useLocale();

  async function loadLibrary() {
    try {
      setLoading(true);
      setError('');
      const items = await listStimuli();
      setSets(items.map(parseStimulusSetSummary));
    } catch (err) {
      setError(localizeOperatorError(t, err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadLibrary();
  }, []);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError('');
    setResult(null);
    try {
      setIsUploading(true);
      const form = new FormData(e.currentTarget);
      const json = await uploadStimuli(form);
      setResult(json);
      await loadLibrary();
    } catch (err) {
      setError(localizeOperatorError(t, err));
    } finally {
      setIsUploading(false);
    }
  }

  const validCount = useMemo(() => sets.filter((s) => s.validation_status === 'valid').length, [sets]);
  const warningCount = useMemo(() => sets.filter((s) => s.validation_status === 'warning_only').length, [sets]);
  const invalidCount = useMemo(() => sets.filter((s) => s.validation_status === 'invalid').length, [sets]);

  return (
    <section>
      <h2>{t('upload.title')}</h2>
      <p className="muted">{t('upload.workflowHint')}</p>

      <section className="panel">
        <h3>{t('upload.summaryTitle')}</h3>
        <div className="summary-grid">
          <SummaryCard label={t('upload.summaryTotal')} value={String(sets.length)} tone="info" />
          <SummaryCard label={t('upload.summaryValid')} value={String(validCount)} tone="good" />
          <SummaryCard label={t('upload.summaryWarnings')} value={String(warningCount)} tone="warn" />
          <SummaryCard label={t('upload.summaryInvalid')} value={String(invalidCount)} tone="bad" />
        </div>
      </section>

      <section className="panel">
        <h3>{t('upload.submit')}</h3>
        <form onSubmit={onSubmit} className="form-row" aria-label={t('upload.submit')}>
          <input name="name" placeholder={t('upload.name')} required />
          <select name="source_format" defaultValue="jsonl" aria-label={t('upload.tableSource')}>
            <option value="jsonl">jsonl</option>
            <option value="csv">csv</option>
          </select>
          <input name="file" type="file" required />
          <button className="primary-btn" type="submit" disabled={isUploading}>
            {isUploading ? t('upload.uploading') : t('upload.submit')}
          </button>
          <button className="secondary-btn" type="button" onClick={loadLibrary} disabled={loading}>
            {t('upload.loadRecent')}
          </button>
        </form>
      </section>

      {loading ? <p>{t('upload.loadingLibrary')}</p> : null}
      {error ? (
        <p role="alert" className="alert-error">
          {error}
        </p>
      ) : null}

      {result ? (
        <section className="panel" aria-live="polite">
          <h3>{t('upload.resultTitle')}</h3>
          <p>
            {t('upload.validationStatus')}:{' '}
            <StatusBadge label={localizeStatus(t, result.validation_status ?? (result.ok ? 'valid' : 'invalid'))} tone={validationTone(String(result.validation_status ?? 'unknown'))} />
          </p>
          <p>
            {t('upload.resultSetId')}: <KbdMono>{String(result.stimulus_set_id ?? t('common.na'))}</KbdMono>
          </p>
          <p>{t('upload.resultItems')}: {String(result.n_items ?? 0)}</p>
          <p>{t('upload.resultTaskFamily')}: {String(result.task_family ?? 'n/a')}</p>
          {Array.isArray(result.errors) && result.errors.length > 0 ? <p>{t('upload.resultHasErrors')}</p> : <p>{t('upload.resultReady')}</p>}
        </section>
      ) : null}

      <section className="panel">
        <h3>{t('upload.recentTitle')}</h3>
        {!loading && sets.length === 0 ? <p>{t('upload.emptyState')}</p> : null}
        {sets.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t('upload.tableName')}</th>
                  <th>{t('upload.tableValidation')}</th>
                  <th>{t('upload.tableItems')}</th>
                  <th>{t('upload.tableTaskFamily')}</th>
                  <th>{t('upload.tableSource')}</th>
                  <th>{t('upload.tableSetId')}</th>
                </tr>
              </thead>
              <tbody>
                {sets.map((setItem) => (
                  <tr key={setItem.stimulus_set_id}>
                    <td>{setItem.name}</td>
                    <td>
                      <StatusBadge label={localizeStatus(t, setItem.validation_status)} tone={validationTone(setItem.validation_status)} />
                    </td>
                    <td>{setItem.n_items}</td>
                    <td>{setItem.task_family}</td>
                    <td>{setItem.source_format}</td>
                    <td>
                      <KbdMono>{setItem.stimulus_set_id}</KbdMono>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </section>
  );
}
