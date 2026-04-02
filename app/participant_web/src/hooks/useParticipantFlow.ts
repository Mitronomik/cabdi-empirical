import { useMemo, useRef, useState } from 'react';

import {
  createSession,
  fetchNextTrial,
  startSession,
  submitBlockQuestionnaire,
  submitTrial,
} from '../lib/api';
import type { QuestionnairePayload, TrialPayload } from '../lib/types';

type Stage = 'consent' | 'instructions' | 'trial' | 'questionnaire' | 'completion';

const DEFAULT_EXPERIMENT_ID = 'pilot_scam_not_scam_v1';
const TOTAL_TRIALS = 54;

export function useParticipantFlow() {
  const [stage, setStage] = useState<Stage>('consent');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentTrial, setCurrentTrial] = useState<TrialPayload | null>(null);
  const [questionnaireBlockId, setQuestionnaireBlockId] = useState<string | null>(null);
  const [completedTrials, setCompletedTrials] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completionCode, setCompletionCode] = useState<string | null>(null);

  const trialStartMsRef = useRef<number>(0);

  const progress = useMemo(() => ({
    completedTrials,
    totalTrials: TOTAL_TRIALS,
    currentOrdinal: Math.min(completedTrials + 1, TOTAL_TRIALS),
  }), [completedTrials]);

  async function loadNextTrial(activeSessionId: string) {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchNextTrial(activeSessionId);
      if ('status' in next && next.status === 'completed') {
        setStage('completion');
        setCurrentTrial(null);
        setCompletionCode(activeSessionId.slice(0, 8).toUpperCase());
        return;
      }
      setCurrentTrial(next);
      setStage('trial');
      trialStartMsRef.current = performance.now();
    } catch (err: unknown) {
      const e = err as { status?: number; detail?: unknown };
      if (e.status === 409 && typeof e.detail === 'object' && e.detail && 'block_id' in e.detail) {
        setQuestionnaireBlockId(String((e.detail as { block_id: string }).block_id));
        setStage('questionnaire');
        setCurrentTrial(null);
      } else {
        setError('Could not load the next trial. Please retry.');
      }
    } finally {
      setLoading(false);
    }
  }

  async function beginSession(participantId: string) {
    setLoading(true);
    setError(null);
    try {
      const created = await createSession(DEFAULT_EXPERIMENT_ID, participantId);
      setSessionId(created.session_id);
      await startSession(created.session_id);
      await loadNextTrial(created.session_id);
    } catch {
      setError('Unable to start session. Please retry.');
      setLoading(false);
    }
  }

  async function submitCurrentTrial(params: {
    humanResponse: string;
    selfConfidence: number;
    reasonClicked: boolean;
    evidenceOpened: boolean;
    verificationCompleted: boolean;
  }) {
    if (!sessionId || !currentTrial) {
      setError('Missing session state. Please restart this participant run.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const reactionTime = Math.max(1, Math.round(performance.now() - trialStartMsRef.current));
      await submitTrial(sessionId, currentTrial.trial_id, {
        human_response: params.humanResponse,
        reaction_time_ms: reactionTime,
        self_confidence: params.selfConfidence,
        reason_clicked: params.reasonClicked,
        evidence_opened: params.evidenceOpened,
        verification_completed: params.verificationCompleted,
      });
      setCompletedTrials((count) => count + 1);
      await loadNextTrial(sessionId);
    } catch {
      setError('Could not submit trial. Please retry submit.');
      setLoading(false);
    }
  }

  async function submitQuestionnaire(payload: QuestionnairePayload) {
    if (!sessionId || !questionnaireBlockId) {
      setError('Missing session state for questionnaire. Please restart this participant run.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await submitBlockQuestionnaire(sessionId, questionnaireBlockId, payload);
      setQuestionnaireBlockId(null);
      await loadNextTrial(sessionId);
    } catch {
      setError('Could not submit questionnaire. Please retry.');
      setLoading(false);
    }
  }

  return {
    stage,
    currentTrial,
    questionnaireBlockId,
    progress,
    loading,
    error,
    completionCode,
    setStage,
    beginSession,
    submitCurrentTrial,
    submitQuestionnaire,
    retryCurrent: () => (sessionId ? loadNextTrial(sessionId) : setError('Missing session state.')),
  };
}
