import { useState } from 'react';

import type { PolicyDecision, StimulusItem } from '../lib/types';

interface Props {
  policyDecision: PolicyDecision;
  stimulus: StimulusItem;
  onReasonClick: () => void;
  onEvidenceOpen: () => void;
  verificationChecked: boolean;
  setVerificationChecked: (value: boolean) => void;
}

function densityClass(compressionMode: PolicyDecision['compression_mode']): string {
  if (compressionMode === 'high') return 'panel density-high';
  if (compressionMode === 'medium') return 'panel density-medium';
  return 'panel density-none';
}

export function AssistancePanel({
  policyDecision,
  stimulus,
  onReasonClick,
  onEvidenceOpen,
  verificationChecked,
  setVerificationChecked,
}: Props) {
  const [rationaleRevealed, setRationaleRevealed] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  const rationaleText = String(stimulus.payload.rationale ?? 'Model reasoning summary unavailable.');
  const evidenceText = String(stimulus.payload.evidence ?? 'Evidence snippets are not available for this item.');

  return (
    <aside className={densityClass(policyDecision.compression_mode)} aria-label="AI assistance panel">
      <h3>AI Assistance</h3>
      {policyDecision.show_prediction && (
        <p>
          <strong>Prediction:</strong> {stimulus.model_prediction}
        </p>
      )}
      {policyDecision.show_confidence && (
        <p>
          <strong>Model confidence:</strong> {stimulus.model_confidence}
        </p>
      )}

      {policyDecision.show_rationale === 'inline' && (
        <p data-testid="rationale-inline">
          <strong>Rationale:</strong> {rationaleText}
        </p>
      )}

      {policyDecision.show_rationale === 'on_click' && (
        <div>
          <button
            type="button"
            onClick={() => {
              setRationaleRevealed(true);
              onReasonClick();
            }}
          >
            Show rationale
          </button>
          {rationaleRevealed && (
            <p data-testid="rationale-on-click">
              <strong>Rationale:</strong> {rationaleText}
            </p>
          )}
        </div>
      )}

      {policyDecision.show_evidence && (
        <div>
          <button
            type="button"
            onClick={() => {
              const next = !evidenceOpen;
              setEvidenceOpen(next);
              if (next) {
                onEvidenceOpen();
              }
            }}
          >
            {evidenceOpen ? 'Hide evidence' : 'Show evidence'}
          </button>
          {evidenceOpen && <p data-testid="evidence-content">{evidenceText}</p>}
        </div>
      )}

      {policyDecision.verification_mode === 'soft_prompt' && (
        <p className="verify-hint">Reminder: the AI can be wrong. Verify before submitting.</p>
      )}

      {policyDecision.verification_mode === 'forced_checkbox' && (
        <label>
          <input
            type="checkbox"
            checked={verificationChecked}
            onChange={(e) => setVerificationChecked(e.target.checked)}
          />
          I reviewed the AI output and made an independent judgment.
        </label>
      )}

      {policyDecision.verification_mode === 'forced_second_look' && (
        <button type="button" onClick={() => setVerificationChecked(true)}>
          Mark second look complete
        </button>
      )}
    </aside>
  );
}
