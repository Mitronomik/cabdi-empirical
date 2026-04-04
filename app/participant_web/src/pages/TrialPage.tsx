import { useState } from 'react';

import { AssistancePanel } from '../components/AssistancePanel';
import { useLocale } from '../i18n/useLocale';
import type { TrialPayload } from '../lib/types';

interface Props {
  trial: TrialPayload;
  loading: boolean;
  onSubmit: (params: {
    humanResponse: string;
    selfConfidence: number;
    reasonClicked: boolean;
    evidenceOpened: boolean;
    verificationCompleted: boolean;
  }) => void;
}

function formatResponseOption(value: string, t: (key: string) => string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === 'scam') return t('trial.response.scam');
  if (normalized === 'not_scam') return t('trial.response.notScam');
  if (normalized === 'yes') return t('trial.response.yes');
  if (normalized === 'no') return t('trial.response.no');
  return value;
}

export function TrialPage({ trial, loading, onSubmit }: Props) {
  const { t } = useLocale();
  const [selectedResponse, setSelectedResponse] = useState<string>('');
  const [selfConfidence, setSelfConfidence] = useState<number>(50);
  const [reasonClicked, setReasonClicked] = useState(false);
  const [evidenceOpened, setEvidenceOpened] = useState(false);
  const [verificationCompleted, setVerificationCompleted] = useState(false);

  const responseOptions = Array.isArray(trial.stimulus.payload.response_options)
    ? (trial.stimulus.payload.response_options as string[])
    : ['scam', 'not_scam'];
  const stimulusTitle = String(trial.stimulus.payload.title ?? t('trial.caseTitle'));
  const stimulusBody = String(trial.stimulus.payload.body ?? trial.stimulus.payload.prompt ?? t('trial.noPrompt'));

  const progress = trial.progress ?? { completed_trials: 0, total_trials: 0, current_ordinal: 0 };
  const currentOrdinal = Math.max(1, Number(progress.current_ordinal || 1));
  const totalTrials = Math.max(currentOrdinal, Number(progress.total_trials || 1));
  const progressPct = Math.round((Math.max(0, currentOrdinal - 1) / Math.max(totalTrials, 1)) * 100);

  const verificationRequired =
    trial.policy_decision.verification_mode === 'forced_checkbox' ||
    trial.policy_decision.verification_mode === 'forced_second_look';

  const canSubmit = Boolean(selectedResponse) && (!verificationRequired || verificationCompleted);

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

      <div className="trial-grid">
        <article className="card stimulus-card">
          <h2>{stimulusTitle}</h2>
          <p>{stimulusBody}</p>
        </article>

        <AssistancePanel
          policyDecision={trial.policy_decision}
          stimulus={trial.stimulus}
          onReasonClick={() => setReasonClicked(true)}
          onEvidenceOpen={() => setEvidenceOpened(true)}
          verificationChecked={verificationCompleted}
          setVerificationChecked={setVerificationCompleted}
        />
      </div>

      <section className="card">
        <h3>{t('trial.decisionTitle')}</h3>
        <div className="button-row">
          {responseOptions.map((option) => (
            <button
              key={option}
              type="button"
              className={selectedResponse === option ? 'selected' : ''}
              onClick={() => setSelectedResponse(option)}
            >
              {formatResponseOption(option, t as unknown as (key: string) => string)}
            </button>
          ))}
        </div>

        {selectedResponse && (
          <>
            <label htmlFor="confidence">
              {t('trial.selfConfidence')} ({selfConfidence})
            </label>
            <input
              id="confidence"
              type="range"
              min={trial.self_confidence_scale.min}
              max={trial.self_confidence_scale.max}
              step={trial.self_confidence_scale.step}
              value={selfConfidence}
              onChange={(e) => setSelfConfidence(Number(e.target.value))}
            />
          </>
        )}

        <button
          type="button"
          disabled={!canSubmit || loading}
          onClick={() =>
            onSubmit({
              humanResponse: selectedResponse,
              selfConfidence,
              reasonClicked,
              evidenceOpened,
              verificationCompleted,
            })
          }
        >
          {t('trial.submit')}
        </button>
      </section>
    </section>
  );
}
