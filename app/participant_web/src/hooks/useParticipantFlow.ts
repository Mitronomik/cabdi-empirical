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

interface PublicRunInfo {
  run_slug: string;
  public_title: string;
  public_description?: string;
  launchable: boolean;
  run_status: string;
}

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
    | 'error.finalSubmit'
    | 'error.runSlugRequired'
    | 'error.runSlugInvalid'
    | 'error.runNotOpen',
) {
  const locale = getCurrentLocale();
  return messages[locale][key];
}

function resolveRunSlugFromUrl(): string {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get('run_slug') ?? params.get('run');
  if (fromQuery && fromQuery.trim()) {
    return fromQuery.trim();
  }
  const match = window.location.pathname.match(/\/(?:r|run|join)\/([^/]+)/i);
  if (match?.[1]) {
    return decodeURIComponent(match[1]).trim();
  }
  return (import.meta.env.VITE_PARTICIPANT_RUN_SLUG ?? '').trim();
}

function toFriendlyError(detail: unknown): string {
  if (typeof detail !== 'string') {
    return localizedError('error.startSession');
  }
  if (detail.includes('Unknown run_slug')) {
    return localizedError('error.runSlugInvalid');
  }
  if (detail.includes('run_slug is required')) {
    return localizedError('error.runSlugRequired');
  }
  if (detail.includes('not launchable')) {
    return localizedError('error.runNotOpen');
  }
  return detail;
}

function resumeStorageKey(runSlug: string): string {
  return `participant_web.resume_token.${runSlug}`;
}

export function useParticipantFlow() {
  const [stage, setStage] = useState<Stage>('consent');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentTrial, setCurrentTrial] = useState<TrialPayload | null>(null);
  const [questionnaireBlockId, setQuestionnaireBlockId] = useState<string | null>(null);
  const [progress, setProgress] = useState({ completedTrials: 0, totalTrials: 0, currentOrdinal: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completionCode, setCompletionCode] = useState<string | null>(null);
  const [runSlug] = useState(resolveRunSlugFromUrl);
  const [publicRun, setPublicRun] = useState<PublicRunInfo | null>(null);

  const trialStartMsRef = useRef<number>(0);

  const onboardingReady = useMemo(() => Boolean(runSlug.trim()), [runSlug]);

  function setProgressFromResponse(next: TrialPayload | { progress?: { completed_trials: number; total_trials: number; current_ordinal: number } }) {
    if (!('progress' in next) || !next.progress) return;
    setProgress({
      completedTrials: Number(next.progress.completed_trials ?? 0),
      totalTrials: Number(next.progress.total_trials ?? 0),
      currentOrdinal: Number(next.progress.current_ordinal ?? 0),
    });
  }

  async function loadNextTrial(activeSessionId: string) {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchNextTrial(activeSessionId);
      setProgressFromResponse(next);
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

  async function loadPublicRunInfo() {
    if (!runSlug.trim()) {
      setError(localizedError('error.runSlugRequired'));
      return;
    }
    try {
      const info = await fetchPublicRun(runSlug);
      setPublicRun(info);
      if (!info.launchable) {
        setError(localizedError('error.runNotOpen'));
      }
    } catch (err: unknown) {
      const e = err as { detail?: unknown };
      setError(toFriendlyError(e.detail));
    }
  }

  async function beginSession() {
    if (!runSlug.trim()) {
      setError(localizedError('error.runSlugRequired'));
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const runInfo = publicRun ?? (await fetchPublicRun(runSlug));
      setPublicRun(runInfo);
      const savedResumeToken = window.localStorage.getItem(resumeStorageKey(runSlug));
      let resumeTokenForCreate: string | null = null;
      if (savedResumeToken) {
        const resumeInfo = await fetchResumeInfo(runSlug, savedResumeToken);
        if (resumeInfo.resume_status === 'resumable') {
          resumeTokenForCreate = savedResumeToken;
        }
        if (resumeInfo.resume_status === 'finalized') {
          window.localStorage.removeItem(resumeStorageKey(runSlug));
        }
      }
      const created = await createSession(runSlug, detectLocale(), resumeTokenForCreate);
      setSessionId(created.session_id);
      window.localStorage.setItem(resumeStorageKey(runSlug), created.resume_token);
      await startSession(created.session_id);
      await loadNextTrial(created.session_id);
    } catch (err: unknown) {
      const e = err as { detail?: unknown };
      setError(toFriendlyError(e.detail));
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
    publicRun,
    onboardingReady,
    setStage,
    loadPublicRunInfo,
    beginSession,
    submitCurrentTrial,
    submitQuestionnaire,
    submitFinalSession,
    retryCurrent: () =>
      sessionId ? loadNextTrial(sessionId) : setError(localizedError('error.missingSessionStateShort')),
  };
}
