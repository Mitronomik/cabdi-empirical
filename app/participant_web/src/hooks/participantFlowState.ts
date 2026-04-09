import type { fetchSessionProgress, NextTrialResponseCompleted } from '../lib/api';
import type { TrialPayload } from '../lib/types';

export const participantStages = [
  'consent',
  'instructions',
  'resume_prompt',
  'trial',
  'questionnaire',
  'awaiting_final_submit',
  'completion',
] as const;

export type ParticipantStage = (typeof participantStages)[number];

export type ResumeBannerKey =
  | 'entry.resumeResumed'
  | 'entry.resumeInvalid'
  | 'entry.resumeFinalized'
  | 'entry.resumeNotResumable';

export type ParticipantProgress = {
  completedTrials: number;
  totalTrials: number;
  currentOrdinal: number;
};

export type NextTrialLike = TrialPayload | NextTrialResponseCompleted;
type SessionProgress = Awaited<ReturnType<typeof fetchSessionProgress>>;

export function getResumeBannerKey(status: string): ResumeBannerKey | null {
  if (status === 'resumable') return 'entry.resumeResumed';
  if (status === 'finalized') return 'entry.resumeFinalized';
  if (status === 'invalid') return 'entry.resumeInvalid';
  if (status === 'not_resumable') return 'entry.resumeNotResumable';
  return null;
}

export function stageFromNextTrialResponse(next: NextTrialLike): ParticipantStage {
  if ('status' in next && next.status === 'awaiting_final_submit') {
    return 'awaiting_final_submit';
  }
  if ('status' in next && ['completed', 'finalized'].includes(next.status)) {
    return 'completion';
  }
  return 'trial';
}

export function stageFromSessionProgress(progress: SessionProgress): {
  stage: ParticipantStage;
  questionnaireBlockId: string | null;
} {
  if (progress.current_stage === 'completion' || progress.status === 'finalized') {
    return { stage: 'completion', questionnaireBlockId: null };
  }
  if (progress.current_stage === 'awaiting_final_submit' || progress.status === 'awaiting_final_submit') {
    return { stage: 'awaiting_final_submit', questionnaireBlockId: null };
  }
  if (progress.current_stage === 'questionnaire') {
    const blockNumber = Number(progress.current_block_index) + 1;
    return { stage: 'questionnaire', questionnaireBlockId: `block_${Math.max(1, blockNumber)}` };
  }
  return { stage: 'trial', questionnaireBlockId: null };
}
