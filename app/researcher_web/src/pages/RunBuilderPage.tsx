import React, { useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { createRun } from '../lib/api';

const DEFAULT_CONFIG = {
  n_blocks: 3,
  trials_per_block: 18,
  budget_matching_mode: 'matched',
};

export function RunBuilderPage() {
  const [response, setResponse] = useState('');
  const { t } = useLocale();

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
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
  }

  return (
    <section>
      <h2>{t('run.title')}</h2>
      <form onSubmit={onSubmit}>
        <input name="run_name" placeholder={t('run.name')} required />
        <input name="experiment_id" defaultValue="toy_v1" required />
        <input name="task_family" defaultValue="scam_detection" required />
        <input name="stimulus_set_ids" placeholder={t('run.stimulusSets')} required />
        <input name="notes" placeholder={t('run.notes')} />
        <button type="submit">{t('run.submit')}</button>
      </form>
      <pre>{response}</pre>
    </section>
  );
}
