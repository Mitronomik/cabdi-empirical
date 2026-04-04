import { useState } from 'react';

import { useLocale } from '../i18n/useLocale';
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

function mapOptionLabel(raw: string, t: (key: string) => string): string {
  const normalized = raw.trim().toLowerCase();
  if (normalized === 'scam') return t('trial.response.scam');
  if (normalized === 'not_scam') return t('trial.response.notScam');
  return raw;
}

function mapConfidenceLabel(raw: string, t: (key: string) => string): string {
  const normalized = raw.trim().toLowerCase();
  if (normalized === 'low') return t('assistance.confidence.low');
  if (normalized === 'medium') return t('assistance.confidence.medium');
  if (normalized === 'high') return t('assistance.confidence.high');
  return raw;
}

export function AssistancePanel({
  policyDecision,
  stimulus,
  onReasonClick,
  onEvidenceOpen,
  verificationChecked,
  setVerificationChecked,
}: Props) {
  const { t } = useLocale();
  const [rationaleRevealed, setRationaleRevealed] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  const rationaleText = String(stimulus.payload.rationale ?? t('assistance.defaultRationale'));
  const evidenceText = String(stimulus.payload.evidence ?? t('assistance.defaultEvidence'));

  return (
    <aside className={densityClass(policyDecision.compression_mode)} aria-label={t('assistance.panelAria')}>
      <h3>{t('assistance.title')}</h3>
      {policyDecision.show_prediction && (
        <p>
          <strong>{t('assistance.prediction')}:</strong>{' '}
          {mapOptionLabel(stimulus.model_prediction, t as unknown as (key: string) => string)}
        </p>
      )}
      {policyDecision.show_confidence && (
        <p>
          <strong>{t('assistance.modelConfidence')}:</strong>{' '}
          {mapConfidenceLabel(stimulus.model_confidence, t as unknown as (key: string) => string)}
        </p>
      )}

      {policyDecision.show_rationale === 'inline' && (
        <p data-testid="rationale-inline">
          <strong>{t('assistance.rationale')}:</strong> {rationaleText}
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
            {t('assistance.showRationale')}
          </button>
          {rationaleRevealed && (
            <p data-testid="rationale-on-click">
              <strong>{t('assistance.rationale')}:</strong> {rationaleText}
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
            {evidenceOpen ? t('assistance.hideEvidence') : t('assistance.showEvidence')}
          </button>
          {evidenceOpen && <p data-testid="evidence-content">{evidenceText}</p>}
        </div>
      )}

      {policyDecision.verification_mode === 'soft_prompt' && (
        <p className="verify-hint">{t('assistance.verifyHint')}</p>
      )}

      {policyDecision.verification_mode === 'forced_checkbox' && (
        <label>
          <input
            type="checkbox"
            checked={verificationChecked}
            onChange={(e) => setVerificationChecked(e.target.checked)}
          />
          {t('assistance.forcedCheckbox')}
        </label>
      )}

      {policyDecision.verification_mode === 'forced_second_look' && (
        <button type="button" onClick={() => setVerificationChecked(true)}>
          {t('assistance.secondLook')}
        </button>
      )}
    </aside>
  );
}
