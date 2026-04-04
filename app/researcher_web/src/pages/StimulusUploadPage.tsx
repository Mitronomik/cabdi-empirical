import React, { useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { listStimuli, uploadStimuli } from '../lib/api';

export function StimulusUploadPage() {
  const [result, setResult] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [recentSets, setRecentSets] = useState<Array<Record<string, unknown>>>([]);
  const { t } = useLocale();

  async function loadRecent() {
    try {
      setError('');
      const items = await listStimuli();
      setRecentSets(items.slice(0, 5));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError('');
    setResult('');
    try {
      const formEl = e.currentTarget;
      const form = new FormData(formEl);
      const json = await uploadStimuli(form);
      setResult(JSON.stringify(json, null, 2));
      await loadRecent();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
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
        <button type="submit">{t('upload.submit')}</button>
        <button type="button" onClick={loadRecent}>
          {t('upload.loadRecent')}
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      <pre>{result}</pre>
      <h3>{t('upload.recentTitle')}</h3>
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
