import React, { useEffect, useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { listStimuli, uploadStimuli } from '../lib/api';

export function StimulusUploadPage() {
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [recentSets, setRecentSets] = useState<Array<Record<string, unknown>>>([]);
  const { t } = useLocale();

  async function loadRecent() {
    try {
      setLoading(true);
      setError('');
      const items = await listStimuli();
      setRecentSets(items.slice(0, 5));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadRecent();
  }, []);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError('');
    setResult(null);
    try {
      setIsUploading(true);
      const formEl = e.currentTarget;
      const form = new FormData(formEl);
      const json = await uploadStimuli(form);
      setResult(json);
      await loadRecent();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <section>
      <h2>{t('upload.title')}</h2>
      <form onSubmit={onSubmit}>
        <input name="name" placeholder={t('upload.name')} required />
        <select name="source_format" defaultValue="jsonl">
          <option value="jsonl">jsonl</option>
          <option value="csv">csv</option>
        </select>
        <input name="file" type="file" required />
        <button type="submit" disabled={isUploading}>
          {isUploading ? 'Uploading...' : t('upload.submit')}
        </button>
        <button type="button" onClick={loadRecent} disabled={loading}>
          {t('upload.loadRecent')}
        </button>
      </form>
      {loading ? <p>Loading stimulus library...</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {result ? (
        <div>
          <h3>Upload result</h3>
          <p>status: {String(result.validation_status ?? (result.ok ? 'validated' : 'invalid'))}</p>
          <p>stimulus_set_id: {String(result.stimulus_set_id ?? 'n/a')}</p>
          <p>n_items: {String(result.n_items ?? 0)}</p>
          {Array.isArray(result.warnings) && result.warnings.length > 0 ? (
            <p>warnings: {JSON.stringify(result.warnings)}</p>
          ) : null}
          {Array.isArray(result.errors) && result.errors.length > 0 ? <p>errors: {JSON.stringify(result.errors)}</p> : null}
          {Array.isArray(result.preview_rows) && result.preview_rows.length > 0 ? (
            <pre>{JSON.stringify(result.preview_rows, null, 2)}</pre>
          ) : null}
        </div>
      ) : null}
      <h3>{t('upload.recentTitle')}</h3>
      {!loading && recentSets.length === 0 ? <p>No stimulus banks yet. Upload a bank to continue.</p> : null}
      <ul>
        {recentSets.map((setItem) => (
          <li key={String(setItem.stimulus_set_id)}>
            {String(setItem.stimulus_set_id)} · {String(setItem.name)} · {String(setItem.task_family)} (
            {String(setItem.n_items)})
          </li>
        ))}
      </ul>
    </section>
  );
}
