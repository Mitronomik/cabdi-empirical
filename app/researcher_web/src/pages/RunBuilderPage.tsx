import React, { useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { createRun, listRuns } from '../lib/api';

const DEFAULT_CONFIG = {
  n_blocks: 3,
  trials_per_block: 16,
  budget_matching_mode: 'matched_extra_steps',
};

export function RunBuilderPage() {
  const [response, setResponse] = useState('');
  const [error, setError] = useState('');
  const [recentRuns, setRecentRuns] = useState<Array<Record<string, unknown>>>([]);
  const { t } = useLocale();

  async function loadRecentRuns() {
    try {
      setError('');
      const items = await listRuns();
      setRecentRuns(items.slice(0, 5));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError('');
    setResponse('');
    try {
      const data = new FormData(e.currentTarget);
      const payload = {
        run_name: data.get('run_name'),
        experiment_id: data.get('experiment_id'),
        task_family: data.get('task_family'),
        stimulus_set_ids: String(data.get('stimulus_set_ids') ?? '')
          .split(',')
          .map((x) => x.trim())
          .filter(Boolean),
        config: DEFAULT_CONFIG,
        notes: data.get('notes') || null,
      };
      const out = await createRun(payload);
      setResponse(JSON.stringify(out, null, 2));
      await loadRecentRuns();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }

  return (
    <section>
      <h2>{t('run.title')}</h2>
      <form onSubmit={onSubmit}>
        <input name="run_name" placeholder={t('run.name')} required />
        <input name="experiment_id" defaultValue="pilot_scam_not_scam_v1" required />
        <input name="task_family" defaultValue="scam_not_scam" required />
        <input name="stimulus_set_ids" placeholder={t('run.stimulusSets')} required />
        <input name="notes" placeholder={t('run.notes')} />
        <button type="submit">{t('run.submit')}</button>
        <button type="button" onClick={loadRecentRuns}>
          {t('run.loadRecent')}
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      <pre>{response}</pre>
      <h3>{t('run.recentTitle')}</h3>
      <ul>
        {recentRuns.map((run) => (
          <li key={String(run.run_id)}>
            {String(run.run_id)} · {String(run.run_name)} · {String(run.public_slug)} · {String(run.task_family)}
          </li>
        ))}
      </ul>
    </section>
  );
}
