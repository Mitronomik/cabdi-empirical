import React, { useEffect, useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { listStimuli, uploadStimuli } from '../lib/api';

export function StimulusUploadPage() {
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [sets, setSets] = useState<Array<Record<string, unknown>>>([]);
  const { t } = useLocale();

  async function loadLibrary() {
    try {
      setLoading(true);
      setError('');
      const items = await listStimuli();
      setSets(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
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
        <button type="button" onClick={loadLibrary} disabled={loading}>
          {t('upload.loadRecent')}
        </button>
      </form>

      {loading ? <p>Loading stimulus library...</p> : null}
      {error ? <p role="alert">{error}</p> : null}

      {result ? (
        <div>
          <h3>Upload result</h3>
          <p>validation_status: {String(result.validation_status ?? (result.ok ? 'valid' : 'invalid'))}</p>
          <p>stimulus_set_id: {String(result.stimulus_set_id ?? 'n/a')}</p>
          <p>task_family: {String(result.task_family ?? 'n/a')}</p>
          <p>source_format: {String(result.source_format ?? 'n/a')}</p>
          <p>n_items: {String(result.n_items ?? 0)}</p>
          <p>payload_schema_version: {String(result.payload_schema_version ?? 'n/a')}</p>
          {Array.isArray(result.warnings) && result.warnings.length > 0 ? <pre>warnings: {JSON.stringify(result.warnings, null, 2)}</pre> : null}
          {Array.isArray(result.errors) && result.errors.length > 0 ? <pre>errors: {JSON.stringify(result.errors, null, 2)}</pre> : null}
          {Array.isArray(result.preview_rows) && result.preview_rows.length > 0 ? (
            <>
              <p>preview_rows:</p>
              <pre>{JSON.stringify(result.preview_rows, null, 2)}</pre>
            </>
          ) : null}
        </div>
      ) : null}

      <h3>{t('upload.recentTitle')}</h3>
      {!loading && sets.length === 0 ? <p>No stimulus banks yet. Upload a bank to continue.</p> : null}
      {sets.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>stimulus_set_id</th>
              <th>name</th>
              <th>task_family</th>
              <th>source_format</th>
              <th>n_items</th>
              <th>validation_status</th>
              <th>payload_schema_version</th>
            </tr>
          </thead>
          <tbody>
            {sets.map((setItem) => (
              <tr key={String(setItem.stimulus_set_id)}>
                <td>{String(setItem.stimulus_set_id)}</td>
                <td>{String(setItem.name)}</td>
                <td>{String(setItem.task_family)}</td>
                <td>{String(setItem.source_format)}</td>
                <td>{String(setItem.n_items)}</td>
                <td>{String(setItem.validation_status)}</td>
                <td>{String(setItem.payload_schema_version ?? 'n/a')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
