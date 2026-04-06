import React, { useEffect, useMemo, useState } from 'react';

import { KbdMono, StatusBadge, SummaryCard } from '../components/OperatorPrimitives';
import { localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { activateRun, closeRun, createRun, getRunBuilderDefaults, listRuns, listStimuli, pauseRun } from '../lib/api';
import { parseRunSummary, parseStimulusSetSummary } from '../lib/researcherUi';

function runTone(status: string): 'good' | 'warn' | 'bad' | 'neutral' {
  if (status === 'active') return 'good';
  if (status === 'paused' || status === 'draft') return 'warn';
  if (status === 'closed') return 'bad';
  return 'neutral';
}

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
  const [selectedMainStimulusSetIds, setSelectedMainStimulusSetIds] = useState<string[]>([]);
  const [selectedPracticeStimulusSetId, setSelectedPracticeStimulusSetId] = useState('');
  const [aggregationEnabled, setAggregationEnabled] = useState(false);
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

  const activeRuns = useMemo(() => recentRuns.filter((r) => r.status === 'active').length, [recentRuns]);
  const pausedRuns = useMemo(() => recentRuns.filter((r) => r.status === 'paused').length, [recentRuns]);
  const draftRuns = useMemo(() => recentRuns.filter((r) => r.status === 'draft').length, [recentRuns]);

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
        setSelectedMainStimulusSetIds((prev) => (prev.length > 0 ? prev : [defaultSetId]));
      } else {
        setSelectedStimulusSetId('');
        setSelectedMainStimulusSetIds([]);
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
    const mainSetIds = aggregationEnabled ? selectedMainStimulusSetIds : [selectedStimulusSetId].filter(Boolean);
    if (mainSetIds.length === 0) {
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
        stimulus_set_ids: mainSetIds,
        aggregation_mode: aggregationEnabled ? 'multi' : 'single',
        practice_stimulus_set_id: selectedPracticeStimulusSetId || null,
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

  const selectedMainStimuli = useMemo(
    () => validStimulusSets.filter((item) => selectedMainStimulusSetIds.includes(String(item.stimulus_set_id))),
    [selectedMainStimulusSetIds, validStimulusSets],
  );
  const selectedConfig = ((selectedPreset?.config as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const executionConfig = ((selectedConfig.execution as Record<string, unknown> | undefined) ?? {}) as Record<string, unknown>;
  const expectedTrialCount =
    Number(selectedConfig.trials_per_block ?? executionConfig.trials_per_block ?? 0) *
      Number(selectedConfig.n_blocks ?? executionConfig.n_blocks ?? 0) +
    Number(executionConfig.practice_trials ?? 0);

  return (
    <section>
      <h2>{t('run.title')}</h2>
      <p className="muted">{t('run.workflowHint')}</p>
      {loading ? <p>{t('run.loading')}</p> : null}

      <section className="panel">
        <h3>{t('run.summaryTitle')}</h3>
        <div className="summary-grid">
          <SummaryCard label={t('run.summaryValidatedStimuli')} value={String(validStimulusSets.length)} tone="good" />
          <SummaryCard label={t('run.summaryActive')} value={String(activeRuns)} tone="good" />
          <SummaryCard label={t('run.summaryPaused')} value={String(pausedRuns)} tone="warn" />
          <SummaryCard label={t('run.summaryDraft')} value={String(draftRuns)} tone="info" />
        </div>
      </section>

      {!loading && stimulusSets.length === 0 ? <p>{t('run.emptyNoStimulus')}</p> : null}
      {!loading && stimulusSets.length > 0 && validStimulusSets.length === 0 ? <p>{t('run.emptyNoValidStimulus')}</p> : null}

      <section className="panel">
        <h3>{t('run.createPanelTitle')}</h3>
        <form onSubmit={onSubmit}>
          <div className="form-row">
            <input name="run_name" value={runName} onChange={(e) => setRunName(e.target.value)} placeholder={t('run.name')} required />
            <input name="public_slug" value={publicSlug} onChange={(e) => setPublicSlug(e.target.value)} placeholder={t('run.slug')} />
            <input value={String(defaults?.experiment_id ?? '')} readOnly aria-label={t('run.experimentId')} />
            <input value={String(selectedStimulus?.task_family ?? defaults?.task_family ?? '')} readOnly aria-label={t('run.taskFamily')} />
          </div>
          <div className="form-row" style={{ marginTop: 8 }}>
            <select value={selectedStimulusSetId} onChange={(e) => {
              setSelectedStimulusSetId(e.target.value);
              if (!aggregationEnabled) setSelectedMainStimulusSetIds(e.target.value ? [e.target.value] : []);
            }} required>
              <option value="">{t('run.selectStimulus')}</option>
              {validStimulusSets.map((item) => (
                <option key={item.stimulus_set_id} value={item.stimulus_set_id}>
                  {item.name} • {item.task_family} • {item.n_items} • {localizeStatus(t, item.validation_status)}
                </option>
              ))}
            </select>
            <input name="notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={t('run.notes')} />
            <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <input type="checkbox" checked={aggregationEnabled} onChange={(e) => {
                const next = e.target.checked;
                setAggregationEnabled(next);
                if (!next) {
                  setSelectedMainStimulusSetIds(selectedStimulusSetId ? [selectedStimulusSetId] : []);
                }
              }} />
              Aggregation mode
            </label>
            <button className="primary-btn" type="submit" disabled={isCreating || validStimulusSets.length === 0}>
              {isCreating ? t('run.creating') : t('run.submit')}
            </button>
            <button className="secondary-btn" type="button" onClick={loadDependencies} disabled={loading}>
              {t('run.loadRecent')}
            </button>
          </div>
          {aggregationEnabled ? (
            <div className="form-row" style={{ marginTop: 8 }}>
              <select
                multiple
                value={selectedMainStimulusSetIds}
                onChange={(e) => setSelectedMainStimulusSetIds(Array.from(e.target.selectedOptions).map((o) => o.value))}
              >
                {validStimulusSets.map((item) => (
                  <option key={`main-${item.stimulus_set_id}`} value={item.stimulus_set_id}>
                    {item.name} • {item.n_items}
                  </option>
                ))}
              </select>
              <select value={selectedPracticeStimulusSetId} onChange={(e) => setSelectedPracticeStimulusSetId(e.target.value)}>
                <option value="">Practice bank (optional)</option>
                {validStimulusSets.map((item) => (
                  <option key={`practice-${item.stimulus_set_id}`} value={item.stimulus_set_id}>
                    {item.name} • {item.n_items}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
        </form>
      </section>

      {selectedStimulus ? (
        <p>
          {t('run.selectedStimulusSummary')}: {selectedStimulus.name} ({selectedStimulus.n_items} items, {localizeStatus(t, selectedStimulus.validation_status)}) ·{' '}
          <KbdMono>{selectedStimulus.stimulus_set_id}</KbdMono>
        </p>
      ) : null}
      <section className="panel">
        <h3>Run summary before activation</h3>
        <p>Practice bank: {selectedPracticeStimulusSetId || 'none'}</p>
        <p>Main bank(s): {(aggregationEnabled ? selectedMainStimulusSetIds : [selectedStimulusSetId]).filter(Boolean).join(', ') || 'none'}</p>
        <p>Aggregation: {aggregationEnabled ? 'enabled (explicit)' : 'disabled (single-select)'}</p>
        <p>Total main items: {selectedMainStimuli.reduce((acc, item) => acc + Number(item.n_items || 0), 0)}</p>
        <p>Expected trial count: {expectedTrialCount}</p>
      </section>
      {error ? (
        <p role="alert" className="alert-error">
          {error}
        </p>
      ) : null}
      {success ? <p className="alert-success">{success}</p> : null}
      {response ? (
        <section className="panel" aria-live="polite">
          <h3>{t('run.createResultTitle')}</h3>
          <p>{t('run.tableRunName')}: {String(response.run_name)}</p>
          <p>{t('run.tableSlug')}: {String(response.public_slug)}</p>
          <p>
            {t('run.tableStatus')}: <StatusBadge label={localizeStatus(t, response.status)} tone={runTone(String(response.status ?? 'unknown'))} />
          </p>
          <p>
            {t('run.tableRunId')}: <KbdMono>{String(response.run_id)}</KbdMono>
          </p>
        </section>
      ) : null}

      <section className="panel">
        <h3>{t('run.recentTitle')}</h3>
        <p className="muted">{t('run.recentHint')}</p>
        {recentRuns.length === 0 ? <p>{t('run.emptyNoRuns')}</p> : null}
        {recentRuns.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t('run.tableRunName')}</th>
                  <th>{t('run.tableStatus')}</th>
                  <th>{t('run.tableSlug')}</th>
                  <th>{t('run.tableStimulus')}</th>
                  <th>{t('run.tableLaunchability')}</th>
                  <th>{t('run.tableActions')}</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((run) => {
                  const runId = run.run_id;
                  const status = run.status;
                  return (
                    <tr key={runId}>
                      <td>
                        {run.run_name}
                        <div>
                          <KbdMono>{runId}</KbdMono>
                        </div>
                      </td>
                      <td>
                        <StatusBadge label={localizeStatus(t, status)} tone={runTone(status)} />
                      </td>
                      <td>{run.public_slug ? `/${run.public_slug}` : t('common.na')}</td>
                      <td>{run.linked_stimulus_set_ids.join(', ') || t('common.na')} ({run.aggregation_mode ?? 'single'})</td>
                      <td>{run.launchability_reason}</td>
                      <td>
                        <div className="toolbar">
                          <button
                            className="primary-btn"
                            disabled={(status !== 'draft' && status !== 'paused') || lifecycleLoadingRunId === runId}
                            onClick={() => onLifecycle(runId, 'activate')}
                          >
                            {t('run.activate')}
                          </button>
                          <button className="secondary-btn" disabled={status !== 'active' || lifecycleLoadingRunId === runId} onClick={() => onLifecycle(runId, 'pause')}>
                            {t('run.pause')}
                          </button>
                          <button className="danger-btn" disabled={status === 'closed' || lifecycleLoadingRunId === runId} onClick={() => onLifecycle(runId, 'close')}>
                            {t('run.close')}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </section>
  );
}
