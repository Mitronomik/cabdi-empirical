import { useMemo, useRef, useState } from 'react';

import {
  createSession,
  fetchResumeInfo,
  fetchPublicRun,
  fetchNextTrial,
  finalSubmitSession,
  startSession,
  submitBlockQuestionnaire,
  submitTrial,
} from '../lib/api';
import { detectLocale } from '../i18n/locale';
import { messages, type Locale } from '../i18n/messages';
import type { QuestionnairePayload, TrialPayload } from '../lib/types';

type Stage = 'consent' | 'instructions' | 'trial' | 'questionnaire' | 'awaiting_final_submit' | 'completion';

function getCurrentLocale(): Locale {
  return detectLocale();
}

function localizedError(
  key:
    | 'error.loadNextTrial'
    | 'error.startSession'
    | 'error.missingSessionState'
    | 'error.submitTrial'
    | 'error.missingQuestionnaireState'
    | 'error.submitQuestionnaire'
    | 'error.missingSessionStateShort'
    | 'error.finalSubmit',
) {
  const locale = getCurrentLocale();
  return messages[locale][key];
}

function detailError(detail: unknown): string | null {
  return typeof detail === 'string' ? detail : null;
}

function resumeStorageKey(runSlug: string): string {
  return `participant_web.resume_token.${runSlug}`;
}

export function useParticipantFlow() {
  const [stage, setStage] = useState<Stage>('consent');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentTrial, setCurrentTrial] = useState<TrialPayload | null>(null);
  const [questionnaireBlockId, setQuestionnaireBlockId] = useState<string | null>(null);
  const [completedTrials, setCompletedTrials] = useState(0);
  const [totalTrials, setTotalTrials] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completionCode, setCompletionCode] = useState<string | null>(null);
  const [runSlug, setRunSlug] = useState(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('run_slug');
    if (fromUrl && fromUrl.trim()) {
      return fromUrl.trim();
    }
    return import.meta.env.VITE_PARTICIPANT_RUN_SLUG ?? '';
  });

  const trialStartMsRef = useRef<number>(0);

  const progress = useMemo(() => ({
    completedTrials,
    totalTrials: Math.max(totalTrials, completedTrials + 1),
    currentOrdinal: Math.min(completedTrials + 1, Math.max(totalTrials, completedTrials + 1)),
  }), [completedTrials, totalTrials]);

  async function loadNextTrial(activeSessionId: string) {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchNextTrial(activeSessionId);
      if ('progress' in next && next.progress) {
        setCompletedTrials(Number(next.progress.completed_trials ?? 0));
        setTotalTrials(Math.max(1, Number(next.progress.total_trials ?? 1)));
      }
      if ('status' in next && next.status === 'awaiting_final_submit') {
        setStage('awaiting_final_submit');
        setCurrentTrial(null);
        return;
      }
      if ('status' in next && ['completed', 'finalized'].includes(next.status)) {
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
        setError(localizedError('error.loadNextTrial'));
      }
    } finally {
      setLoading(false);
    }
  }

  async function beginSession(activeRunSlug: string) {
    const normalizedRunSlug = activeRunSlug.trim();
    if (!normalizedRunSlug) {
      setError('run_slug is required');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await fetchPublicRun(normalizedRunSlug);
      const savedResumeToken = window.localStorage.getItem(resumeStorageKey(normalizedRunSlug));
      let resumeTokenForCreate: string | null = null;
      if (savedResumeToken) {
        const resumeInfo = await fetchResumeInfo(normalizedRunSlug, savedResumeToken);
        if (resumeInfo.resume_status === 'resumable') {
          resumeTokenForCreate = savedResumeToken;
        }
        if (resumeInfo.resume_status === 'finalized') {
          window.localStorage.removeItem(resumeStorageKey(normalizedRunSlug));
        }
      }
      const created = await createSession(normalizedRunSlug, detectLocale(), resumeTokenForCreate);
      setSessionId(created.session_id);
      setCompletedTrials(0);
      setTotalTrials(1);
      window.localStorage.setItem(resumeStorageKey(normalizedRunSlug), created.resume_token);
      await startSession(created.session_id);
      await loadNextTrial(created.session_id);
    } catch (err: unknown) {
      const e = err as { detail?: unknown };
      setError(detailError(e.detail) ?? localizedError('error.startSession'));
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
      setError(localizedError('error.missingSessionState'));
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
      setError(localizedError('error.submitTrial'));
      setLoading(false);
    }
  }

  async function submitQuestionnaire(payload: QuestionnairePayload) {
    if (!sessionId || !questionnaireBlockId) {
      setError(localizedError('error.missingQuestionnaireState'));
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await submitBlockQuestionnaire(sessionId, questionnaireBlockId, payload);
      setQuestionnaireBlockId(null);
      await loadNextTrial(sessionId);
    } catch {
      setError(localizedError('error.submitQuestionnaire'));
      setLoading(false);
    }
  }

  async function submitFinalSession() {
    if (!sessionId) {
      setError(localizedError('error.missingSessionStateShort'));
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await finalSubmitSession(sessionId);
      if (res.status === 'finalized') {
        setStage('completion');
        setCompletionCode(sessionId.slice(0, 8).toUpperCase());
        if (runSlug.trim()) {
          window.localStorage.removeItem(resumeStorageKey(runSlug.trim()));
        }
      }
    } catch {
      setError(localizedError('error.finalSubmit'));
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
    runSlug,
    setRunSlug,
    setStage,
    beginSession,
    submitCurrentTrial,
    submitQuestionnaire,
    submitFinalSession,
    retryCurrent: () =>
      sessionId ? loadNextTrial(sessionId) : setError(localizedError('error.missingSessionStateShort')),
  };
}
