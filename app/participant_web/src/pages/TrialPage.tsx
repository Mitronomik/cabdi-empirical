import { useEffect, useMemo, useRef, useState } from 'react';

import { AssistancePanel } from '../components/AssistancePanel';
import { useLocale } from '../i18n/useLocale';
import { getRenderableResponseOptions } from '../lib/taskFamilyRegistry';
import type { TrialPayload } from '../lib/types';

interface Props {
  trial: TrialPayload;
  loading: boolean;
  savedFeedback?: boolean;
  onSubmit: (params: {
    humanResponse: string;
    selfConfidence: number;
    reasonClicked: boolean;
    evidenceOpened: boolean;
    verificationCompleted: boolean;
    eventTrace?: Array<{ event_type: string; payload: Record<string, unknown> }>;
  }) => void;
}

interface TrialDraft {
  selectedResponse: string;
  selfConfidence: number | null;
  reasonClicked: boolean;
  evidenceOpened: boolean;
  verificationCompleted: boolean;
}

function trialDraftStorageKey(trialId: string): string {
  return `participant_web.trial_draft.${trialId}`;
}

export function TrialPage({ trial, loading, savedFeedback, onSubmit }: Props) {
  const { t } = useLocale();
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const [selectedResponse, setSelectedResponse] = useState<string>('');
  const [selfConfidence, setSelfConfidence] = useState<number | null>(null);
  const [reasonClicked, setReasonClicked] = useState(false);
  const [evidenceOpened, setEvidenceOpened] = useState(false);
  const [verificationCompleted, setVerificationCompleted] = useState(false);
  const [panelExposure, setPanelExposure] = useState<{ panelVisibleOnFirstPaint: boolean; shownHelpComponents: string[] } | null>(
    null,
  );

  useEffect(() => {
    headingRef.current?.focus();
    const raw = window.sessionStorage.getItem(trialDraftStorageKey(trial.trial_id));
    if (!raw) {
      setSelectedResponse('');
      setSelfConfidence(null);
      setReasonClicked(false);
      setEvidenceOpened(false);
      setVerificationCompleted(false);
      return;
    }

    try {
      const draft = JSON.parse(raw) as Partial<TrialDraft>;
      setSelectedResponse(typeof draft.selectedResponse === 'string' ? draft.selectedResponse : '');
      setSelfConfidence(typeof draft.selfConfidence === 'number' ? draft.selfConfidence : null);
      setReasonClicked(Boolean(draft.reasonClicked));
      setEvidenceOpened(Boolean(draft.evidenceOpened));
      setVerificationCompleted(Boolean(draft.verificationCompleted));
    } catch {
      window.sessionStorage.removeItem(trialDraftStorageKey(trial.trial_id));
    }
  }, [trial.trial_id]);

  useEffect(() => {
    const draft: TrialDraft = {
      selectedResponse,
      selfConfidence,
      reasonClicked,
      evidenceOpened,
      verificationCompleted,
    };
    window.sessionStorage.setItem(trialDraftStorageKey(trial.trial_id), JSON.stringify(draft));
  }, [trial.trial_id, selectedResponse, selfConfidence, reasonClicked, evidenceOpened, verificationCompleted]);

  const responseOptions = useMemo(
    () => getRenderableResponseOptions(trial.stimulus.task_family, trial.stimulus.payload.response_options),
    [trial.stimulus.task_family, trial.stimulus.payload.response_options],
  );
  const hasRenderableResponseOptions = responseOptions.length > 0;
  const stimulusTitle = String(trial.stimulus.payload.title ?? t('trial.caseTitle'));
  const stimulusBody = String(trial.stimulus.payload.body ?? trial.stimulus.payload.prompt ?? t('trial.noPrompt'));

  const progress = trial.progress ?? { completed_trials: 0, total_trials: 0, current_ordinal: 0 };
  const currentOrdinal = Math.max(0, Number(progress.current_ordinal || 0));
  const totalTrials = Math.max(0, Number(progress.total_trials || 0));
  const completedTrials = Math.max(0, Number(progress.completed_trials || 0));
  const progressPct = totalTrials > 0 ? Math.round((Math.min(completedTrials, totalTrials) / totalTrials) * 100) : 0;

  const verificationRequired =
    trial.policy_decision.verification_mode === 'forced_checkbox' ||
    trial.policy_decision.verification_mode === 'forced_second_look';

  const canSubmit = Boolean(selectedResponse) && selfConfidence !== null && (!verificationRequired || verificationCompleted);

  return (
    <section className="trial-shell" data-testid="trial-layout">
      <header className="card progress-card">
        <p>
          {t('trial.progressLabel')} {currentOrdinal} / {totalTrials}
        </p>
        <div className="progress-track" aria-label={t('trial.progressAria')}>
          <div className="progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
        <p className="muted">{t('trial.resumeHint')}</p>
      </header>

      <article className="card stimulus-card">
        <p className="section-kicker">1. {t('trial.caseTitle')}</p>
        <h2 ref={headingRef} tabIndex={-1} className="focus-anchor">{stimulusTitle}</h2>
        <p>{stimulusBody}</p>
      </article>

      <section className="card assistance-card">
        <p className="section-kicker">2. {t('assistance.title')}</p>
        <AssistancePanel
          policyDecision={trial.policy_decision}
          stimulus={trial.stimulus}
          onReasonClick={() => setReasonClicked(true)}
          onEvidenceOpen={() => setEvidenceOpened(true)}
          verificationChecked={verificationCompleted}
          setVerificationChecked={setVerificationCompleted}
          onPanelFirstPaint={setPanelExposure}
        />
      </section>

      <section className="card decision-card">
        <p className="section-kicker">3. {t('trial.decisionTitle')}</p>
        <h3>{t('trial.answerLabel')}</h3>
        <p className="muted">{t('trial.decisionHelp')}</p>

        {hasRenderableResponseOptions ? (
          <fieldset className="response-fieldset" aria-label={t('trial.answerLabel')}>
            <div className="response-grid">
              {responseOptions.map((option) => (
                <label key={option.value} className={`response-option ${selectedResponse === option.value ? 'selected' : ''}`}>
                  <input
                    type="radio"
                    name="human_response"
                    value={option.value}
                    checked={selectedResponse === option.value}
                    onChange={() => setSelectedResponse(option.value)}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
        ) : (
          <p role="alert">Unable to render response options for this trial. Please contact the researcher.</p>
        )}
      </section>

      <section className="card confidence-card">
        <p className="section-kicker">4. {t('trial.selfConfidence')}</p>
        {hasRenderableResponseOptions && (
          <fieldset className="confidence-fieldset" aria-label={t('trial.selfConfidence')}>
            <legend>{t('trial.selfConfidence')}</legend>
            <div className="confidence-grid">
              {[1, 2, 3, 4].map((value) => (
                <label key={value} className={`confidence-option ${selfConfidence === value ? 'selected' : ''}`}>
                  <input
                    type="radio"
                    name="self_confidence"
                    value={value}
                    checked={selfConfidence === value}
                    onChange={() => setSelfConfidence(value)}
                  />
                  <span className="confidence-value">{value}</span>
                  <span className="confidence-text">{t(`trial.confidence.option${value}` as never)}</span>
                </label>
              ))}
            </div>
          </fieldset>
        )}
      </section>

      <footer className="trial-submit-bar">
        <div aria-live="polite">
          <p className="muted submit-hint">5. {t('trial.submitHelp')}</p>
          {savedFeedback ? <p className="muted submit-state">{t('common.progressSaved')}</p> : null}
          {!savedFeedback && !loading ? <p className="muted submit-state">Changes are local until submitted.</p> : null}
        </div>
        <button
          type="button"
          className="primary-submit"
          disabled={!canSubmit || loading}
          onClick={() => {
            onSubmit({
              humanResponse: selectedResponse,
              selfConfidence: selfConfidence as number,
              reasonClicked,
              evidenceOpened,
              verificationCompleted,
              eventTrace: panelExposure
                ? [
                    {
                      event_type: 'assistance_rendered',
                      payload: {
                        assistance_rendered: true,
                        panel_visible_on_first_paint: panelExposure.panelVisibleOnFirstPaint,
                        shown_help_components: panelExposure.shownHelpComponents,
                      },
                    },
                  ]
                : undefined,
            });
          }}
        >
          {loading ? `${t('trial.submit')}...` : t('trial.submit')}
        </button>
      </footer>
    </section>
  );
}
