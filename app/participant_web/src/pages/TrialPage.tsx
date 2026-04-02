import { useState } from 'react';

import { AssistancePanel } from '../components/AssistancePanel';
import type { TrialPayload } from '../lib/types';

interface Props {
  trial: TrialPayload;
  completedTrials: number;
  totalTrials: number;
  loading: boolean;
  onSubmit: (params: {
    humanResponse: string;
    selfConfidence: number;
    reasonClicked: boolean;
    evidenceOpened: boolean;
    verificationCompleted: boolean;
  }) => void;
}

export function TrialPage({ trial, completedTrials, totalTrials, loading, onSubmit }: Props) {
  const [selectedResponse, setSelectedResponse] = useState<string>('');
  const [selfConfidence, setSelfConfidence] = useState<number>(50);
  const [reasonClicked, setReasonClicked] = useState(false);
  const [evidenceOpened, setEvidenceOpened] = useState(false);
  const [verificationCompleted, setVerificationCompleted] = useState(false);

  const responseOptions = Array.isArray(trial.stimulus.payload.response_options)
    ? (trial.stimulus.payload.response_options as string[])
    : ['scam', 'not_scam'];

  const progressPct = Math.round((completedTrials / totalTrials) * 100);

  const verificationRequired =
    trial.policy_decision.verification_mode === 'forced_checkbox' ||
    trial.policy_decision.verification_mode === 'forced_second_look';

  const canSubmit = Boolean(selectedResponse) && (!verificationRequired || verificationCompleted);

  return (
    <section className="trial-shell" data-testid="trial-layout">
      <header>
        <p>
          Trial {Math.min(completedTrials + 1, totalTrials)} / {totalTrials}
        </p>
        <div className="progress-track" aria-label="progress">
          <div className="progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
      </header>

      <div className="trial-grid">
        <article className="card stimulus-card">
          <h2>Case</h2>
          <p>{String(trial.stimulus.payload.prompt ?? 'No prompt provided.')}</p>
          <small>Block: {trial.block_id}</small>
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
        <h3>Your decision</h3>
        <div className="button-row">
          {responseOptions.map((option) => (
            <button
              key={option}
              type="button"
              className={selectedResponse === option ? 'selected' : ''}
              onClick={() => setSelectedResponse(option)}
            >
              {option}
            </button>
          ))}
        </div>

        {selectedResponse && (
          <>
            <label htmlFor="confidence">Self-confidence ({selfConfidence})</label>
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
          Submit trial
        </button>
      </section>
    </section>
  );
}
