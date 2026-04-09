import { useMemo, useState } from 'react';

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

export function TrialPage({ trial, loading, savedFeedback, onSubmit }: Props) {
  const { t } = useLocale();
  const [selectedResponse, setSelectedResponse] = useState<string>('');
  const [selfConfidence, setSelfConfidence] = useState<number | null>(null);
  const [reasonClicked, setReasonClicked] = useState(false);
  const [evidenceOpened, setEvidenceOpened] = useState(false);
  const [verificationCompleted, setVerificationCompleted] = useState(false);
  const [panelExposure, setPanelExposure] = useState<{ panelVisibleOnFirstPaint: boolean; shownHelpComponents: string[] } | null>(
    null,
  );

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
        <h2>{stimulusTitle}</h2>
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
          <div className="button-row">
            {responseOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={selectedResponse === option.value ? 'selected' : ''}
                onClick={() => setSelectedResponse(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
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
        <div>
          <p className="muted submit-hint">5. {t('trial.submitHelp')}</p>
          {savedFeedback ? <p className="muted submit-state">{t('common.progressSaved')}</p> : null}
        </div>
        <button
          type="button"
          className="primary-submit"
          disabled={!canSubmit || loading}
          onClick={() =>
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
            })
          }
        >
          {loading ? `${t('trial.submit')}...` : t('trial.submit')}
        </button>
      </footer>
    </section>
  );
}
