import { useEffect, useMemo, useRef, useState } from 'react';

import { useLocale } from '../i18n/useLocale';
import { formatModelPredictionLabel } from '../lib/taskFamilyRegistry';
import type { PolicyDecision, StimulusItem } from '../lib/types';

interface Props {
  policyDecision: PolicyDecision;
  stimulus: StimulusItem;
  onReasonClick: () => void;
  onEvidenceOpen: () => void;
  verificationChecked: boolean;
  setVerificationChecked: (value: boolean) => void;
  onPanelFirstPaint: (payload: { panelVisibleOnFirstPaint: boolean; shownHelpComponents: string[] }) => void;
}

function densityClass(compressionMode: PolicyDecision['compression_mode']): string {
  if (compressionMode === 'high') return 'panel density-high';
  if (compressionMode === 'medium') return 'panel density-medium';
  return 'panel density-none';
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
  onPanelFirstPaint,
}: Props) {
  const { t } = useLocale();
  const [rationaleRevealed, setRationaleRevealed] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const panelRef = useRef<HTMLElement | null>(null);

  const rationaleText = String(stimulus.payload.rationale ?? t('assistance.defaultRationale'));
  const evidenceText = String(stimulus.payload.evidence ?? t('assistance.defaultEvidence'));
  const shownHelpComponents = useMemo(() => {
    const components: string[] = [];
    if (policyDecision.show_prediction) components.push('prediction');
    if (policyDecision.show_confidence) components.push('confidence');
    if (policyDecision.show_rationale !== 'none') components.push('rationale');
    if (policyDecision.show_evidence) components.push('evidence');
    return components;
  }, [policyDecision]);

  useEffect(() => {
    const rect = panelRef.current?.getBoundingClientRect();
    const panelVisibleOnFirstPaint = Boolean(rect && rect.top < window.innerHeight && rect.bottom > 0);
    onPanelFirstPaint({ panelVisibleOnFirstPaint, shownHelpComponents });
  }, [onPanelFirstPaint, shownHelpComponents]);

  useEffect(() => {
    setRationaleRevealed(false);
    setEvidenceOpen(false);
  }, [stimulus.stimulus_id]);

  return (
    <aside
      ref={panelRef}
      className={`${densityClass(policyDecision.compression_mode)} assistance-salient`}
      aria-label={t('assistance.panelAria')}
      data-testid="assistance-panel"
    >
      <p className="panel-kicker">{t('assistance.panelKicker')}</p>
      <h3>{t('assistance.title')}</h3>
      {policyDecision.show_prediction && (
        <p>
          <strong>{t('assistance.prediction')}:</strong>{' '}
          {formatModelPredictionLabel(stimulus.model_prediction, stimulus.task_family)}
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
        <div className="verification-block" data-testid="verification-required">
          <p className="verify-hint">{t('assistance.verifyHint')}</p>
          <label className="verification-check">
            <input
              type="checkbox"
              checked={verificationChecked}
              onChange={(e) => setVerificationChecked(e.target.checked)}
            />
            {t('assistance.forcedCheckbox')}
          </label>
        </div>
      )}

      {policyDecision.verification_mode === 'forced_second_look' && (
        <div className="verification-block" data-testid="verification-required">
          <p className="verify-hint">{t('assistance.verifyHint')}</p>
          <button type="button" onClick={() => setVerificationChecked(true)} disabled={verificationChecked}>
            {verificationChecked ? `${t('assistance.secondLook')} ✓` : t('assistance.secondLook')}
          </button>
        </div>
      )}
    </aside>
  );
}
