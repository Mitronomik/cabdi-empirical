import React, { useEffect, useState } from 'react';

import { localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { listStimuli, uploadStimuli } from '../lib/api';
import { parseStimulusSetSummary } from '../lib/researcherUi';

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

  return (
    <section>
      <h2>{t('upload.title')}</h2>
      <p>{t('upload.workflowHint')}</p>
      <form onSubmit={onSubmit}>
        <input name="name" placeholder={t('upload.name')} required />
        <select name="source_format" defaultValue="jsonl">
          <option value="jsonl">jsonl</option>
          <option value="csv">csv</option>
        </select>
        <input name="file" type="file" required />
        <button type="submit" disabled={isUploading}>
          {isUploading ? t('upload.uploading') : t('upload.submit')}
        </button>
        <button type="button" onClick={loadLibrary} disabled={loading}>
          {t('upload.loadRecent')}
        </button>
      </form>

      {loading ? <p>{t('upload.loadingLibrary')}</p> : null}
      {error ? <p role="alert">{error}</p> : null}

      {result ? (
        <div>
          <h3>{t('upload.resultTitle')}</h3>
          <p>{t('upload.validationStatus')}: {localizeStatus(t, result.validation_status ?? (result.ok ? 'valid' : 'invalid'))}</p>
          <p>{t('upload.resultSetId')}: {String(result.stimulus_set_id ?? t('common.na'))}</p>
          <p>{t('upload.resultItems')}: {String(result.n_items ?? 0)}</p>
          <p>{t('upload.resultTaskFamily')}: {String(result.task_family ?? 'n/a')}</p>
          {Array.isArray(result.errors) && result.errors.length > 0 ? <p>{t('upload.resultHasErrors')}</p> : <p>{t('upload.resultReady')}</p>}
        </div>
      ) : null}

      <h3>{t('upload.recentTitle')}</h3>
      {!loading && sets.length === 0 ? <p>{t('upload.emptyState')}</p> : null}
      {sets.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>{t('upload.tableName')}</th>
              <th>{t('upload.tableTaskFamily')}</th>
              <th>{t('upload.tableItems')}</th>
              <th>{t('upload.tableValidation')}</th>
              <th>{t('upload.tableSource')}</th>
              <th>{t('upload.tableSetId')}</th>
            </tr>
          </thead>
          <tbody>
            {sets.map((setItem) => (
              <tr key={setItem.stimulus_set_id}>
                <td>{setItem.name}</td>
                <td>{setItem.task_family}</td>
                <td>{setItem.n_items}</td>
                <td>{localizeStatus(t, setItem.validation_status)}</td>
                <td>{setItem.source_format}</td>
                <td>{setItem.stimulus_set_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
