import React, { useEffect, useMemo, useRef, useState } from 'react';

import { KbdMono, StatusBadge, SummaryCard } from '../components/OperatorPrimitives';
import { localizeOperatorError, localizeStatus } from '../i18n/uiText';
import { useLocale } from '../i18n/useLocale';
import { activateRun, closeRun, createRun, getRun, getRunBuilderDefaults, listRuns, listStimuli, pauseRun, previewRun } from '../lib/api';
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
  const [selectedRunId, setSelectedRunId] = useState('');
  const [runDetails, setRunDetails] = useState<ReturnType<typeof parseRunSummary> | null>(null);
  const [runDetailsLoading, setRunDetailsLoading] = useState(false);
  const [runDetailsLoadingRunId, setRunDetailsLoadingRunId] = useState('');
  const [copySuccess, setCopySuccess] = useState('');
  const [selectedMainStimulusSetIds, setSelectedMainStimulusSetIds] = useState<string[]>([]);
  const [selectedPracticeStimulusSetId, setSelectedPracticeStimulusSetId] = useState('');
  const [aggregationEnabled, setAggregationEnabled] = useState(false);
  const [runName, setRunName] = useState(`run-${new Date().toISOString().slice(0, 16).replace('T', '-')}`);
  const [publicSlug, setPublicSlug] = useState('');
  const [notes, setNotes] = useState('');
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const { t } = useLocale();
  const latestRunDetailsRequest = useRef(0);
  const latestPreviewRequest = useRef(0);

  const validStimulusSets = useMemo(
    () => stimulusSets.filter((item) => ['valid', 'warning_only'].includes(String(item.validation_status ?? ''))),
    [stimulusSets],
  );

  const configPresetOptions = (defaults?.config_preset_options as Array<Record<string, unknown>> | undefined) ?? [];
  const selectedPreset = configPresetOptions[0] ?? null;

  const activeRuns = useMemo(() => recentRuns.filter((r) => r.status === 'active').length, [recentRuns]);
  const pausedRuns = useMemo(() => recentRuns.filter((r) => r.status === 'paused').length, [recentRuns]);
  const draftRuns = useMemo(() => recentRuns.filter((r) => r.status === 'draft').length, [recentRuns]);

  async function loadRecentRuns() {
    const items = await listRuns();
    const parsedRuns = items.slice(0, 20).map(parseRunSummary);
    setRecentRuns(parsedRuns);
    if (parsedRuns.length === 0) {
      setSelectedRunId('');
      setRunDetails(null);
      return;
    }
    const nextSelected = selectedRunId && parsedRuns.some((run) => run.run_id === selectedRunId) ? selectedRunId : parsedRuns[0].run_id;
    setSelectedRunId(nextSelected);
  }

  async function loadRunDetails(runId: string) {
    if (!runId) {
      setRunDetails(null);
      setRunDetailsLoadingRunId('');
      return;
    }
    const requestId = latestRunDetailsRequest.current + 1;
    latestRunDetailsRequest.current = requestId;
    setRunDetailsLoading(true);
    setRunDetailsLoadingRunId(runId);
    try {
      const details = await getRun(runId);
      if (latestRunDetailsRequest.current === requestId) {
        setRunDetails(parseRunSummary(details));
      }
    } finally {
      if (latestRunDetailsRequest.current === requestId) {
        setRunDetailsLoading(false);
        setRunDetailsLoadingRunId('');
      }
    }
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
        setSelectedMainStimulusSetIds((prev) => (prev.length > 0 ? prev : [defaultSetId]));
      } else {
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

  useEffect(() => {
    if (!selectedRunId) return;
    void loadRunDetails(selectedRunId);
  }, [selectedRunId]);

  async function onDetails(runId: string) {
    setCopySuccess('');
    setSelectedRunId(runId);
    await loadRunDetails(runId);
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError('');
    setSuccess('');
    setResponse(null);
    const mainSetIds = selectedMainSetIds;
    if (mainSetIds.length === 0) {
      setError(t('run.errorMissingStimulus'));
      return;
    }
    if (previewValidationErrors.length > 0) {
      setError(previewValidationErrors[0]);
      return;
    }
    try {
      setIsCreating(true);
      const experimentId = String(defaults?.experiment_id ?? '').trim();
      if (!experimentId) {
        setError(t('run.errorMissingDefaults'));
        return;
      }
      const payload = {
        run_name: runName.trim(),
        public_slug: publicSlug.trim() || null,
        experiment_id: experimentId,
        task_family: preview?.resolved_task_family ? String(preview.resolved_task_family) : null,
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
      if (out.run_id) {
        const newRunId = String(out.run_id);
        setSelectedRunId(newRunId);
        await loadRunDetails(newRunId);
      }
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
      await loadRunDetails(runId);
    } catch (err) {
      setError(localizeOperatorError(t, err));
    } finally {
      setLifecycleLoadingRunId('');
    }
  }

  const selectedPracticeStimulus = useMemo(
    () => validStimulusSets.find((item) => String(item.stimulus_set_id) === selectedPracticeStimulusSetId),
    [selectedPracticeStimulusSetId, validStimulusSets],
  );
  const availableMainStimulusSets = useMemo(
    () => validStimulusSets.filter((item) => String(item.stimulus_set_id) !== selectedPracticeStimulusSetId),
    [selectedPracticeStimulusSetId, validStimulusSets],
  );
  const selectedSingleMainSetId = selectedMainStimulusSetIds[0] ?? '';
  const selectedMainSetIds = useMemo(
    () => {
      const availableIds = new Set(availableMainStimulusSets.map((item) => String(item.stimulus_set_id)));
      const deduped = selectedMainStimulusSetIds.filter((id, idx, arr) => id && arr.indexOf(id) === idx && availableIds.has(id));
      return aggregationEnabled ? deduped : deduped.slice(0, 1);
    },
    [aggregationEnabled, availableMainStimulusSets, selectedMainStimulusSetIds],
  );
  const selectedMainBanks = useMemo(
    () => validStimulusSets.filter((item) => selectedMainSetIds.includes(String(item.stimulus_set_id))),
    [selectedMainSetIds, validStimulusSets],
  );
  const availablePracticeStimulusSets = useMemo(
    () => validStimulusSets.filter((item) => !selectedMainSetIds.includes(String(item.stimulus_set_id))),
    [selectedMainSetIds, validStimulusSets],
  );
  const selectedMainTaskFamilies = useMemo(
    () => Array.from(new Set(selectedMainBanks.map((item) => String(item.task_family || '').trim()).filter(Boolean))),
    [selectedMainBanks],
  );
  const mainTaskFamilyMixed = selectedMainTaskFamilies.length > 1;
  const derivedMainTaskFamily = selectedMainTaskFamilies.length === 1 ? selectedMainTaskFamilies[0] : '';
  const taskFamilyFieldValue = mainTaskFamilyMixed
    ? 'mixed task families (invalid)'
    : selectedMainSetIds.length === 0
      ? 'no main bank selected'
      : (derivedMainTaskFamily || 'no main bank selected');
  const selectedMainSummary = selectedMainBanks.map((bank) => `${bank.name} (${bank.n_items})`).join(', ') || 'none';
  const selectedSingleMainBank = !aggregationEnabled && selectedMainBanks.length === 1 ? selectedMainBanks[0] : null;
  const practiceItemCount = Number(preview?.practice_item_count ?? 0);
  const mainItemCount = Number(preview?.main_item_count ?? 0);
  const expectedTrialCount = Number(preview?.expected_trial_count ?? 0);
  const previewValidationErrors = Array.isArray(preview?.validation_errors) ? preview.validation_errors.map((item) => String(item)) : [];
  const previewWarnings = Array.isArray(preview?.operator_warnings) ? preview.operator_warnings.map((item) => String(item)) : [];
  const previewBlockWarnings = Array.isArray(preview?.block_shape_warnings) ? preview.block_shape_warnings.map((item) => String(item)) : [];

  async function refreshPreview() {
    const experimentId = String(defaults?.experiment_id ?? '').trim();
    if (!experimentId) return;
    const requestId = latestPreviewRequest.current + 1;
    latestPreviewRequest.current = requestId;
    try {
      const nextPreview = await previewRun({
        run_name: runName.trim(),
        public_slug: publicSlug.trim() || null,
        experiment_id: experimentId,
        task_family: derivedMainTaskFamily || null,
        stimulus_set_ids: selectedMainSetIds,
        aggregation_mode: aggregationEnabled ? 'multi' : 'single',
        practice_stimulus_set_id: selectedPracticeStimulusSetId || null,
        config: (selectedPreset?.config as Record<string, unknown>) ?? {},
        notes: notes.trim() || null,
      });
      if (latestPreviewRequest.current === requestId) {
        setPreview(nextPreview);
      }
    } catch {
      // preview errors are surfaced from response payload; network failures are non-fatal for builder inputs
    }
  }

  useEffect(() => {
    if (aggregationEnabled) return;
    if (selectedSingleMainSetId) return;
    const firstAvailable = availableMainStimulusSets[0];
    if (firstAvailable) setSelectedMainStimulusSetIds([String(firstAvailable.stimulus_set_id)]);
  }, [aggregationEnabled, availableMainStimulusSets, selectedSingleMainSetId]);

  useEffect(() => {
    void refreshPreview();
  }, [defaults, runName, publicSlug, selectedMainSetIds.join(','), aggregationEnabled, selectedPracticeStimulusSetId, notes]);

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
          <section className="subsection">
            <h4>Run basics</h4>
            <div className="form-row">
              <input name="run_name" value={runName} onChange={(e) => setRunName(e.target.value)} placeholder={t('run.name')} required />
              <input name="public_slug" value={publicSlug} onChange={(e) => setPublicSlug(e.target.value)} placeholder={t('run.slug')} />
              <input name="notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={t('run.notes')} />
              <input value={String(defaults?.experiment_id ?? '')} readOnly aria-label={t('run.experimentId')} />
              <input value={taskFamilyFieldValue} readOnly aria-label={t('run.taskFamily')} />
            </div>
          </section>
          <section className="subsection">
            <h4>Main and practice bank selection</h4>
            <p className="muted" style={{ margin: 0 }}>
              Main bank(s) are required. Practice bank is optional and supplementary only.
            </p>
            <div className="form-row" style={{ marginTop: 8 }}>
              {!aggregationEnabled ? (
                <select
                  aria-label="Main bank"
                  value={selectedSingleMainSetId}
                  onChange={(e) => setSelectedMainStimulusSetIds(e.target.value ? [e.target.value] : [])}
                  required
                >
                  <option value="">{t('run.selectStimulus')}</option>
                  {availableMainStimulusSets.map((item) => (
                    <option key={item.stimulus_set_id} value={item.stimulus_set_id}>
                      {item.name} • {item.task_family} • {item.n_items} • {localizeStatus(t, item.validation_status)}
                    </option>
                  ))}
                </select>
              ) : (
                <select
                  aria-label="Main banks"
                  multiple
                  value={selectedMainStimulusSetIds}
                  onChange={(e) => setSelectedMainStimulusSetIds(Array.from(e.target.selectedOptions).map((o) => o.value))}
                >
                  {availableMainStimulusSets.map((item) => (
                    <option key={`main-${item.stimulus_set_id}`} value={item.stimulus_set_id}>
                      {item.name} • {item.n_items}
                    </option>
                  ))}
                </select>
              )}
              <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <input type="checkbox" checked={aggregationEnabled} onChange={(e) => {
                  const next = e.target.checked;
                  setAggregationEnabled(next);
                  if (!next) {
                    setSelectedMainStimulusSetIds((prev) => {
                      const availableIds = new Set(availableMainStimulusSets.map((item) => String(item.stimulus_set_id)));
                      const firstStillAvailable = prev.find((id) => availableIds.has(id));
                      return firstStillAvailable ? [firstStillAvailable] : [];
                    });
                  }
                }} />
                Aggregation mode
              </label>
              <select value={selectedPracticeStimulusSetId} onChange={(e) => setSelectedPracticeStimulusSetId(e.target.value)}>
                <option value="">Practice bank (optional supplementary)</option>
                {availablePracticeStimulusSets.map((item) => (
                  <option key={`practice-${item.stimulus_set_id}`} value={item.stimulus_set_id}>
                    {item.name} • {item.n_items}
                  </option>
                ))}
              </select>
            </div>
          </section>
          <section className="subsection">
            <h4>Prelaunch summary</h4>
            <div className="summary-grid">
              <SummaryCard label="Practice bank items" value={String(practiceItemCount)} tone="info" />
              <SummaryCard label="Main bank items" value={String(mainItemCount)} tone="info" />
              <SummaryCard label="Expected total trials" value={String(expectedTrialCount)} tone="warn" />
              <SummaryCard label="Aggregation mode" value={aggregationEnabled ? 'multi-bank' : 'single-bank'} tone={aggregationEnabled ? 'warn' : 'good'} />
            </div>
            <p>Selected practice bank: {selectedPracticeStimulus ? `${selectedPracticeStimulus.name} (${practiceItemCount})` : 'none'}</p>
            <p>Selected main banks: {selectedMainSummary}</p>
            {previewValidationErrors.length > 0 ? (
              <p role="alert" className="alert-error">{previewValidationErrors[0]}</p>
            ) : null}
            {previewWarnings.length > 0 ? <p className="muted">Operator warning: {previewWarnings.join('; ')}</p> : null}
            {previewBlockWarnings.length > 0 ? <p className="muted">Block warning: {previewBlockWarnings.join('; ')}</p> : null}
            <div className="toolbar">
              <button className="primary-btn" type="submit" disabled={isCreating || validStimulusSets.length === 0}>
                {isCreating ? t('run.creating') : t('run.submit')}
              </button>
              <button className="secondary-btn" type="button" onClick={loadDependencies} disabled={loading}>
                {t('run.loadRecent')}
              </button>
            </div>
          </section>
          <div className="form-row" style={{ marginTop: 8 }}>
            {mainTaskFamilyMixed ? (
              <p role="alert" className="alert-error">
                Selected main banks have mixed task families. Choose banks with one shared task family before creating a run.
              </p>
            ) : null}
          </div>
        </form>
      </section>

      {selectedSingleMainBank ? (
        <p>
          {t('run.selectedStimulusSummary')}: {selectedSingleMainBank.name} ({selectedSingleMainBank.n_items} items,{' '}
          {localizeStatus(t, selectedSingleMainBank.validation_status)}) · <KbdMono>{selectedSingleMainBank.stimulus_set_id}</KbdMono>
        </p>
      ) : null}
      <section className="panel">
        <h3>Run summary before activation</h3>
        <p>Practice bank: {selectedPracticeStimulus ? `${selectedPracticeStimulus.name} (${practiceItemCount})` : 'none'}</p>
        <p>Main bank(s): {selectedMainSummary}</p>
        <p>Aggregation: {aggregationEnabled ? 'enabled (explicit)' : 'disabled (single-select)'}</p>
        <p>Total practice items: {practiceItemCount}</p>
        <p>Total main items: {mainItemCount}</p>
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
      {runDetails ? (
        <section className="panel" aria-live="polite">
          <h3>Run details</h3>
          <p>
            Selected run: <KbdMono>{selectedRunId}</KbdMono>
          </p>
          {runDetailsLoading && runDetailsLoadingRunId === selectedRunId ? <p className="muted">Refreshing run details…</p> : null}
          <p>
            {t('run.tableRunName')}: {runDetails.run_name} · <KbdMono>{runDetails.run_id}</KbdMono>
          </p>
          <p>
            {t('run.tableStatus')}: <StatusBadge label={localizeStatus(t, runDetails.run_status)} tone={runTone(runDetails.run_status)} /> ·{' '}
            {runDetails.launchability_state}
          </p>
          <p>
            Participant link: <KbdMono>{runDetails.invite_url || t('common.na')}</KbdMono>
          </p>
          <p>
            {t('run.tableSlug')}: <KbdMono>{runDetails.public_slug || t('common.na')}</KbdMono>
          </p>
          <div className="toolbar">
            <button
              className="secondary-btn"
              type="button"
              onClick={async () => {
                if (!runDetails.invite_url) return;
                await navigator.clipboard.writeText(runDetails.invite_url);
                setCopySuccess('Participant link copied.');
              }}
              disabled={!runDetails.invite_url}
            >
              Copy link
            </button>
            <button
              className="secondary-btn"
              type="button"
              onClick={() => {
                if (!runDetails.invite_url) return;
                window.open(runDetails.invite_url, '_blank', 'noopener,noreferrer');
              }}
              disabled={!runDetails.invite_url}
            >
              Open link
            </button>
            {copySuccess ? <span className="muted">{copySuccess}</span> : null}
          </div>
          <p>Activation state: {runDetails.launchable ? 'accepting new sessions' : 'not accepting new sessions'}</p>
          <p>
            Selected banks:{' '}
            {runDetails.run_summary?.banks?.map((bank) => `${bank.name} (${bank.role}, ${bank.n_items})`).join(', ') || t('common.na')}
          </p>
          <p>Selected practice bank: {runDetails.run_summary?.selected_practice_bank?.name ?? runDetails.run_summary?.practice_bank?.name ?? 'none'}</p>
          <p>Total practice items: {String(runDetails.run_summary?.practice_item_count ?? '0')}</p>
          <p>Total main items: {String(runDetails.run_summary?.total_main_items ?? t('common.na'))}</p>
          <p>Expected trial count: {String(runDetails.run_summary?.expected_trial_count ?? t('common.na'))}</p>
        </section>
      ) : null}

      <section className="panel">
        <h3>Recent runs and run details</h3>
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
                          <button className="secondary-btn" onClick={() => void onDetails(runId)}>
                            Details
                          </button>
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
