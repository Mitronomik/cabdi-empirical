import { describe, expect, it } from 'vitest';

import { getResumeBannerKey, stageFromNextTrialResponse, stageFromSessionProgress } from '../hooks/participantFlowState';

describe('participant flow state helpers', () => {
  it('maps resume statuses to banner keys', () => {
    expect(getResumeBannerKey('resumable')).toBe('entry.resumeResumed');
    expect(getResumeBannerKey('finalized')).toBe('entry.resumeFinalized');
    expect(getResumeBannerKey('invalid')).toBe('entry.resumeInvalid');
    expect(getResumeBannerKey('not_resumable')).toBe('entry.resumeNotResumable');
    expect(getResumeBannerKey('unknown')).toBeNull();
  });

  it('maps next-trial payloads to participant stages', () => {
    expect(stageFromNextTrialResponse({ status: 'awaiting_final_submit' })).toBe('awaiting_final_submit');
    expect(stageFromNextTrialResponse({ status: 'completed' })).toBe('completion');
    expect(stageFromNextTrialResponse({ status: 'finalized' })).toBe('completion');
    expect(
      stageFromNextTrialResponse({
        block_id: 'practice',
        trial_id: 't1',
        stimulus: {
          stimulus_id: 's1',
          task_family: 'task',
          content_type: 'text',
          payload: {},
          true_label: 'a',
          difficulty_prior: 'low',
          model_prediction: 'a',
          model_confidence: 'low',
          model_correct: true,
          eligible_sets: ['demo'],
        },
        policy_decision: {
          condition: 'cabdi_lite',
          risk_bucket: 'low',
          show_prediction: true,
          show_confidence: true,
          show_rationale: 'none',
          show_evidence: false,
          verification_mode: 'none',
          compression_mode: 'none',
          max_extra_steps: 0,
          ui_help_level: 'low',
          ui_verification_level: 'low',
          budget_signature: {},
        },
        self_confidence_scale: { type: '4_point', min: 1, max: 4, step: 1 },
        progress: { completed_trials: 0, total_trials: 1, current_ordinal: 1 },
      }),
    ).toBe('trial');
  });

  it('derives resumed session stage and questionnaire block id from progress', () => {
    expect(
      stageFromSessionProgress({
        session_id: 's1',
        status: 'in_progress',
        current_stage: 'questionnaire',
        current_block_index: 0,
        current_trial_index: 3,
      }),
    ).toEqual({ stage: 'questionnaire', questionnaireBlockId: 'block_1' });

    expect(
      stageFromSessionProgress({
        session_id: 's1',
        status: 'awaiting_final_submit',
        current_stage: 'trial',
        current_block_index: 1,
        current_trial_index: 0,
      }),
    ).toEqual({ stage: 'awaiting_final_submit', questionnaireBlockId: null });
  });
});
