import React, { useEffect, useMemo, useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { activateRun, closeRun, createRun, getRunBuilderDefaults, listRuns, listStimuli, pauseRun } from '../lib/api';

type RunRow = Record<string, unknown>;

export function RunBuilderPage() {
  const [response, setResponse] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [lifecycleLoadingRunId, setLifecycleLoadingRunId] = useState('');
  const [stimulusSets, setStimulusSets] = useState<Array<Record<string, unknown>>>([]);
  const [recentRuns, setRecentRuns] = useState<Array<RunRow>>([]);
  const [defaults, setDefaults] = useState<Record<string, unknown> | null>(null);
  const [selectedStimulusSetId, setSelectedStimulusSetId] = useState('');
  const [runName, setRunName] = useState(`run-${new Date().toISOString().slice(0, 16).replace('T', '-')}`);
  const [publicSlug, setPublicSlug] = useState('');
  const [notes, setNotes] = useState('');
  const { t } = useLocale();

  const validStimulusSets = useMemo(
    () => stimulusSets.filter((item) => ['valid', 'warning_only'].includes(String(item.validation_status ?? ''))),
    [stimulusSets],
  );

  const selectedStimulus = useMemo(
    () => validStimulusSets.find((item) => String(item.stimulus_set_id) === selectedStimulusSetId),
    [selectedStimulusSetId, validStimulusSets],
  );

  const configPresetOptions = (defaults?.config_preset_options as Array<Record<string, unknown>> | undefined) ?? [];
  const selectedPreset = configPresetOptions[0] ?? null;

  async function loadRecentRuns() {
    const items = await listRuns();
    setRecentRuns(items.slice(0, 20));
  }

  async function loadDependencies() {
    setLoading(true);
    setError('');
    try {
      const [stimuli, runDefaults] = await Promise.all([listStimuli(), getRunBuilderDefaults(), loadRecentRuns()]);
      const safeStimuli = Array.isArray(stimuli) ? stimuli : [];
      setStimulusSets(safeStimuli);
      setDefaults(runDefaults);

      const firstValid = safeStimuli.find((item) => ['valid', 'warning_only'].includes(String(item.validation_status ?? '')));
      if (firstValid) {
        const defaultSetId = String(firstValid.stimulus_set_id);
        setSelectedStimulusSetId((prev) => prev || defaultSetId);
      } else {
        setSelectedStimulusSetId('');
      }

      if (!publicSlug) {
        setPublicSlug(runName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, ''));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDependencies();
  }, []);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError('');
    setResponse(null);
    if (!selectedStimulusSetId) {
      setError('Select a valid stimulus set before creating a run.');
      return;
    }
    try {
      setIsCreating(true);
      const experimentId = String(defaults?.experiment_id ?? '').trim();
      const taskFamily = String(selectedStimulus?.task_family ?? defaults?.task_family ?? '').trim();
      if (!experimentId || !taskFamily) {
        setError('Missing required system defaults (experiment/task family).');
        return;
      }
      const payload = {
        run_name: runName.trim(),
        public_slug: publicSlug.trim() || null,
        experiment_id: experimentId,
        task_family: taskFamily,
        stimulus_set_ids: [selectedStimulusSetId],
        config: (selectedPreset?.config as Record<string, unknown>) ?? {},
        notes: notes.trim() || null,
      };
      const out = await createRun(payload);
      setResponse(out);
      await loadRecentRuns();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsCreating(false);
    }
  }

  async function onLifecycle(runId: string, action: 'activate' | 'pause' | 'close') {
    setError('');
    try {
      setLifecycleLoadingRunId(runId);
      if (action === 'activate') await activateRun(runId);
      if (action === 'pause') await pauseRun(runId);
      if (action === 'close') await closeRun(runId);
      await loadRecentRuns();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLifecycleLoadingRunId('');
    }
  }

  return (
    <section>
      <h2>{t('run.title')}</h2>
      {loading ? <p>Loading run builder options...</p> : null}
      {!loading && stimulusSets.length === 0 ? <p>No stimulus sets found. Upload a stimulus bank first to create a run.</p> : null}
      {!loading && stimulusSets.length > 0 && validStimulusSets.length === 0 ? (
        <p>Stimulus sets exist but none are run-compatible yet. Upload a valid bank to create a run.</p>
      ) : null}
      <form onSubmit={onSubmit}>
        <input name="run_name" value={runName} onChange={(e) => setRunName(e.target.value)} placeholder={t('run.name')} required />
        <input name="public_slug" value={publicSlug} onChange={(e) => setPublicSlug(e.target.value)} placeholder="public slug" />
        <input value={String(defaults?.experiment_id ?? '')} readOnly />
        <input value={String(selectedStimulus?.task_family ?? defaults?.task_family ?? '')} readOnly />
        <select value={selectedStimulusSetId} onChange={(e) => setSelectedStimulusSetId(e.target.value)} required>
          <option value="">Select valid stimulus set</option>
          {validStimulusSets.map((item) => (
            <option key={String(item.stimulus_set_id)} value={String(item.stimulus_set_id)}>
              {String(item.stimulus_set_id)} · {String(item.name)} · {String(item.task_family)} · {String(item.validation_status)}
            </option>
          ))}
        </select>
        <input name="notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={t('run.notes')} />
        <button type="submit" disabled={isCreating || validStimulusSets.length === 0}>
          {isCreating ? 'Creating...' : t('run.submit')}
        </button>
        <button type="button" onClick={loadDependencies} disabled={loading}>
          {t('run.loadRecent')}
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      {response ? (
        <div>
          <h3>Run create result</h3>
          <p>run_id: {String(response.run_id)}</p>
          <p>public_slug: {String(response.public_slug)}</p>
          <p>status: {String(response.status)}</p>
          <p>task_family: {String(response.task_family)}</p>
          <p>linked stimulus sets: {JSON.stringify(response.linked_stimulus_set_ids ?? [])}</p>
        </div>
      ) : null}
      <h3>{t('run.recentTitle')}</h3>
      {recentRuns.length === 0 ? <p>No runs yet. Create a run to continue.</p> : null}
      {recentRuns.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>run_id</th>
              <th>run_name</th>
              <th>public_slug</th>
              <th>status</th>
              <th>task_family</th>
              <th>linked_stimulus_set_ids</th>
              <th>launchability</th>
              <th>created_at</th>
              <th>actions</th>
            </tr>
          </thead>
          <tbody>
            {recentRuns.map((run) => {
              const runId = String(run.run_id);
              const status = String(run.status);
              return (
                <tr key={runId}>
                  <td>{runId}</td>
                  <td>{String(run.run_name)}</td>
                  <td>{String(run.public_slug)}</td>
                  <td>{status}</td>
                  <td>{String(run.task_family)}</td>
                  <td>{JSON.stringify(run.linked_stimulus_set_ids ?? [])}</td>
                  <td>{String(run.launchability_reason ?? '')}</td>
                  <td>{String(run.created_at)}</td>
                  <td>
                    <button disabled={status !== 'draft' && status !== 'paused' || lifecycleLoadingRunId === runId} onClick={() => onLifecycle(runId, 'activate')}>
                      Activate
                    </button>
                    <button disabled={status !== 'active' || lifecycleLoadingRunId === runId} onClick={() => onLifecycle(runId, 'pause')}>
                      Pause
                    </button>
                    <button disabled={status === 'closed' || lifecycleLoadingRunId === runId} onClick={() => onLifecycle(runId, 'close')}>
                      Close
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
