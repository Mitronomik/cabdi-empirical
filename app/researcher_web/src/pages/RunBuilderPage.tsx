import React, { useEffect, useMemo, useState } from 'react';

import { localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { activateRun, closeRun, createRun, getRunBuilderDefaults, listRuns, listStimuli, pauseRun } from '../lib/api';
import { parseRunSummary, parseStimulusSetSummary } from '../lib/researcherUi';

export function RunBuilderPage() {
  const [response, setResponse] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [lifecycleLoadingRunId, setLifecycleLoadingRunId] = useState('');
  const [stimulusSets, setStimulusSets] = useState<Array<ReturnType<typeof parseStimulusSetSummary>>>([]);
  const [recentRuns, setRecentRuns] = useState<Array<ReturnType<typeof parseRunSummary>>>([]);
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
    setRecentRuns(items.slice(0, 20).map(parseRunSummary));
  }

  async function loadDependencies() {
    setLoading(true);
    setError('');
    try {
      const [stimuli, runDefaults] = await Promise.all([listStimuli(), getRunBuilderDefaults(), loadRecentRuns()]);
      const safeStimuli = Array.isArray(stimuli) ? stimuli.map(parseStimulusSetSummary) : [];
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
      setError(localizeOperatorError(t, err));
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
    setSuccess('');
    setResponse(null);
    if (!selectedStimulusSetId) {
      setError(t('run.errorMissingStimulus'));
      return;
    }
    try {
      setIsCreating(true);
      const experimentId = String(defaults?.experiment_id ?? '').trim();
      const taskFamily = String(selectedStimulus?.task_family ?? defaults?.task_family ?? '').trim();
      if (!experimentId || !taskFamily) {
        setError(t('run.errorMissingDefaults'));
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
      setSuccess(t('run.createSuccess'));
      await loadRecentRuns();
    } catch (err) {
      setError(localizeOperatorError(t, err));
    } finally {
      setIsCreating(false);
    }
  }

  async function onLifecycle(runId: string, action: 'activate' | 'pause' | 'close') {
    setError('');
    setSuccess('');
    try {
      setLifecycleLoadingRunId(runId);
      if (action === 'activate') {
        const proceed = window.confirm(t('run.confirmActivate'));
        if (!proceed) return;
        await activateRun(runId);
        setSuccess(t('run.activateSuccess'));
      }
      if (action === 'pause') {
        const proceed = window.confirm(t('run.confirmPause'));
        if (!proceed) return;
        await pauseRun(runId);
        setSuccess(t('run.pauseSuccess'));
      }
      if (action === 'close') {
        const proceed = window.confirm(`${t('run.confirmClose')} ${runId}`);
        if (!proceed) return;
        await closeRun(runId);
        setSuccess(t('run.closeSuccess'));
      }
      await loadRecentRuns();
    } catch (err) {
      setError(localizeOperatorError(t, err));
    } finally {
      setLifecycleLoadingRunId('');
    }
  }

  return (
    <section>
      <h2>{t('run.title')}</h2>
      <p>{t('run.workflowHint')}</p>
      {loading ? <p>{t('run.loading')}</p> : null}
      {!loading && stimulusSets.length === 0 ? <p>{t('run.emptyNoStimulus')}</p> : null}
      {!loading && stimulusSets.length > 0 && validStimulusSets.length === 0 ? <p>{t('run.emptyNoValidStimulus')}</p> : null}
      <form onSubmit={onSubmit}>
        <input name="run_name" value={runName} onChange={(e) => setRunName(e.target.value)} placeholder={t('run.name')} required />
        <input name="public_slug" value={publicSlug} onChange={(e) => setPublicSlug(e.target.value)} placeholder={t('run.slug')} />
        <input value={String(defaults?.experiment_id ?? '')} readOnly aria-label={t('run.experimentId')} />
        <input value={String(selectedStimulus?.task_family ?? defaults?.task_family ?? '')} readOnly aria-label={t('run.taskFamily')} />
        <select value={selectedStimulusSetId} onChange={(e) => setSelectedStimulusSetId(e.target.value)} required>
          <option value="">{t('run.selectStimulus')}</option>
          {validStimulusSets.map((item) => (
            <option key={item.stimulus_set_id} value={item.stimulus_set_id}>
              {item.name} • {item.task_family} • {item.n_items} • {item.validation_status}
            </option>
          ))}
        </select>
        <input name="notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={t('run.notes')} />
        <button type="submit" disabled={isCreating || validStimulusSets.length === 0}>
          {isCreating ? t('run.creating') : t('run.submit')}
        </button>
        <button type="button" onClick={loadDependencies} disabled={loading}>
          {t('run.loadRecent')}
        </button>
      </form>

      {selectedStimulus ? (
        <p>
          {t('run.selectedStimulusSummary')}: {selectedStimulus.name} ({selectedStimulus.n_items} items, {localizeStatus(t, selectedStimulus.validation_status)}) · {selectedStimulus.stimulus_set_id}
        </p>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
      {success ? <p>{success}</p> : null}
      {response ? (
        <div>
          <h3>{t('run.createResultTitle')}</h3>
          <p>{t('run.tableRunName')}: {String(response.run_name)}</p>
          <p>{t('run.tableSlug')}: {String(response.public_slug)}</p>
          <p>{t('run.tableStatus')}: {localizeStatus(t, response.status)}</p>
          <p>{t('run.tableRunId')}: {String(response.run_id)}</p>
        </div>
      ) : null}
      <h3>{t('run.recentTitle')}</h3>
      {recentRuns.length === 0 ? <p>{t('run.emptyNoRuns')}</p> : null}
      {recentRuns.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>{t('run.tableRunName')}</th>
              <th>{t('run.tableSlug')}</th>
              <th>{t('run.tableStatus')}</th>
              <th>{t('run.tableLaunchability')}</th>
              <th>{t('run.tableStimulus')}</th>
              <th>{t('run.tableRunId')}</th>
              <th>{t('run.tableActions')}</th>
            </tr>
          </thead>
          <tbody>
            {recentRuns.map((run) => {
              const runId = run.run_id;
              const status = run.status;
              return (
                <tr key={runId}>
                  <td>{run.run_name}</td>
                  <td>{run.public_slug}</td>
                  <td>{localizeStatus(t, status)}</td>
                  <td>{run.launchability_reason}</td>
                  <td>{run.linked_stimulus_set_ids.join(', ')}</td>
                  <td>{runId}</td>
                  <td>
                    <button disabled={(status !== 'draft' && status !== 'paused') || lifecycleLoadingRunId === runId} onClick={() => onLifecycle(runId, 'activate')}>
                      {t('run.activate')}
                    </button>
                    <button disabled={status !== 'active' || lifecycleLoadingRunId === runId} onClick={() => onLifecycle(runId, 'pause')}>
                      {t('run.pause')}
                    </button>
                    <button disabled={status === 'closed' || lifecycleLoadingRunId === runId} onClick={() => onLifecycle(runId, 'close')}>
                      {t('run.close')}
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
