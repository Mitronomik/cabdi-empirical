import { useEffect, useMemo, useRef, useState } from 'react';

import {
  createSession,
  fetchResumeInfo,
  fetchSessionProgress,
  fetchPublicRun,
  fetchNextTrial,
  type NextTrialResponseCompleted,
  finalSubmitSession,
  resumeSession,
  startSession,
  submitBlockQuestionnaire,
  submitTrial,
} from '../lib/api';
import { detectLocale } from '../i18n/locale';
import { messages, type Locale } from '../i18n/messages';
import type { QuestionnairePayload, TrialPayload } from '../lib/types';
import {
  type ParticipantProgress,
  type ParticipantStage,
  type ResumeBannerKey,
  getResumeBannerKey,
  stageFromNextTrialResponse,
  stageFromSessionProgress,
} from './participantFlowState';

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
  if (detail.includes('run not found')) {
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

function sessionStorageKey(runSlug: string): string {
  return `participant_web.session_id.${runSlug}`;
}

function isTrialPayload(next: TrialPayload | NextTrialResponseCompleted): next is TrialPayload {
  return 'trial_id' in next;
}

export function useParticipantFlow() {
  const [stage, setStage] = useState<ParticipantStage>('consent');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentTrial, setCurrentTrial] = useState<TrialPayload | null>(null);
  const [questionnaireBlockId, setQuestionnaireBlockId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ParticipantProgress>({ completedTrials: 0, totalTrials: 0, currentOrdinal: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completionCode, setCompletionCode] = useState<string | null>(null);
  const [runSlug] = useState(resolveRunSlugFromUrl);
  const [publicRun, setPublicRun] = useState<PublicRunInfo | null>(null);
  const [resumeBannerKey, setResumeBannerKey] = useState<ResumeBannerKey | null>(null);
  const [savedFeedback, setSavedFeedback] = useState(false);
  const [resumeCandidate, setResumeCandidate] = useState<{ token: string; sessionId?: string } | null>(null);

  const trialStartMsRef = useRef<number>(0);

  function signalSavedFeedback() {
    setSavedFeedback(true);
    window.setTimeout(() => setSavedFeedback(false), 2200);
  }

  const onboardingReady = useMemo(() => Boolean(runSlug.trim()), [runSlug]);

  function updateProgressFromResponse(next: TrialPayload | { progress?: { completed_trials: number; total_trials: number; current_ordinal: number } }) {
    if (!('progress' in next) || !next.progress) return;
    setProgress({
      completedTrials: Number(next.progress.completed_trials ?? 0),
      totalTrials: Number(next.progress.total_trials ?? 0),
      currentOrdinal: Number(next.progress.current_ordinal ?? 0),
    });
  }

  function setCompletionState(activeSessionId: string) {
    setStage('completion');
    setCurrentTrial(null);
    setQuestionnaireBlockId(null);
    setCompletionCode(activeSessionId.slice(0, 8).toUpperCase());
  }

  function setQuestionnaireState(blockId: string) {
    setQuestionnaireBlockId(blockId);
    setCurrentTrial(null);
    setStage('questionnaire');
  }

  async function loadNextTrial(activeSessionId: string) {
    setLoading(true);
    setError(null);
    setSavedFeedback(false);
    try {
      const next = await fetchNextTrial(activeSessionId);
      updateProgressFromResponse(next);

      const nextStage = stageFromNextTrialResponse(next);
      if (nextStage === 'awaiting_final_submit') {
        setStage('awaiting_final_submit');
        setCurrentTrial(null);
        return;
      }
      if (nextStage === 'completion') {
        setCompletionState(activeSessionId);
        return;
      }

      if (!isTrialPayload(next)) {
        setError(localizedError('error.loadNextTrial'));
        return;
      }

      setCurrentTrial(next);
      setQuestionnaireBlockId(null);
      setStage('trial');
      trialStartMsRef.current = performance.now();
    } catch (err: unknown) {
      const e = err as { status?: number; detail?: unknown };
      if (e.status === 409 && typeof e.detail === 'object' && e.detail && 'block_id' in e.detail) {
        setQuestionnaireState(String((e.detail as { block_id: string }).block_id));
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

  async function loadResumeSurfaceHint() {
    if (!runSlug.trim()) return;
    const savedResumeToken = window.localStorage.getItem(resumeStorageKey(runSlug));
    if (!savedResumeToken) return;

    try {
      const resumeInfo = await fetchResumeInfo(runSlug, savedResumeToken);
      const bannerKey = getResumeBannerKey(resumeInfo.resume_status);
      if (bannerKey) {
        setResumeBannerKey(bannerKey);
      }

      if (resumeInfo.resume_status === 'resumable') {
        setResumeCandidate({ token: savedResumeToken, sessionId: resumeInfo.session_id });
        setStage('resume_prompt');
        return;
      }
      if (resumeInfo.resume_status === 'finalized') {
        window.localStorage.removeItem(resumeStorageKey(runSlug));
      }
    } catch {
      // Keep entry flow resilient; run launchability still gates start.
    }
  }

  async function bootstrapPublicRunEntry() {
    if (!runSlug.trim()) return;
    await Promise.all([loadPublicRunInfo(), loadResumeSurfaceHint()]);
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
      if (!runInfo.launchable) {
        setError(localizedError('error.runNotOpen'));
        setLoading(false);
        return;
      }

      const savedResumeToken = window.localStorage.getItem(resumeStorageKey(runSlug));
      let resumeTokenForCreate: string | null = null;
      setResumeBannerKey(null);
      if (savedResumeToken) {
        const resumeInfo = await fetchResumeInfo(runSlug, savedResumeToken);
        const bannerKey = getResumeBannerKey(resumeInfo.resume_status);
        if (bannerKey) {
          setResumeBannerKey(bannerKey);
        }
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
      window.localStorage.setItem(sessionStorageKey(runSlug), created.session_id);
      await startSession(created.session_id);
      await loadNextTrial(created.session_id);
    } catch (err: unknown) {
      const e = err as { detail?: unknown };
      setError(toFriendlyError(e.detail));
      setLoading(false);
    }
  }

  useEffect(() => {
    void bootstrapPublicRunEntry();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runSlug]);

  async function submitCurrentTrial(params: {
    humanResponse: string;
    selfConfidence: number;
    reasonClicked: boolean;
    evidenceOpened: boolean;
    verificationCompleted: boolean;
    eventTrace?: Array<{ event_type: string; payload: Record<string, unknown> }>;
  }) {
    if (!sessionId || !currentTrial) {
      setError(localizedError('error.missingSessionState'));
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const reactionTime = Math.max(1, Math.round(performance.now() - trialStartMsRef.current));
      const res = await submitTrial(sessionId, currentTrial.trial_id, {
        human_response: params.humanResponse,
        reaction_time_ms: reactionTime,
        self_confidence: params.selfConfidence,
        reason_clicked: params.reasonClicked,
        evidence_opened: params.evidenceOpened,
        verification_completed: params.verificationCompleted,
        event_trace: params.eventTrace,
      });
      if (res.saved_ack?.saved) {
        signalSavedFeedback();
      }
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
      const res = await submitBlockQuestionnaire(sessionId, questionnaireBlockId, payload);
      if (res.saved_ack?.saved) {
        signalSavedFeedback();
      }
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
        setCompletionState(sessionId);
        if (runSlug.trim()) {
          window.localStorage.removeItem(resumeStorageKey(runSlug.trim()));
          window.localStorage.removeItem(sessionStorageKey(runSlug.trim()));
        }
      }
    } catch {
      setError(localizedError('error.finalSubmit'));
      setLoading(false);
    }
  }

  async function continueResumedSession() {
    if (!runSlug.trim() || !resumeCandidate?.token) return;
    setLoading(true);
    setError(null);
    try {
      const resumed = await resumeSession(runSlug, resumeCandidate.token);
      if (resumed.resume_status !== 'resumable' || !resumed.session_id) {
        setStage('consent');
        setLoading(false);
        return;
      }

      setSessionId(resumed.session_id);
      window.localStorage.setItem(resumeStorageKey(runSlug), resumeCandidate.token);
      window.localStorage.setItem(sessionStorageKey(runSlug), resumed.session_id);

      const sessionProgress = await fetchSessionProgress(resumed.session_id);
      const resolved = stageFromSessionProgress(sessionProgress);
      if (resolved.stage === 'completion') {
        setCompletionState(resumed.session_id);
        setLoading(false);
        return;
      }
      if (resolved.stage === 'awaiting_final_submit') {
        setStage('awaiting_final_submit');
        setLoading(false);
        return;
      }
      if (resolved.stage === 'questionnaire' && resolved.questionnaireBlockId) {
        setQuestionnaireState(resolved.questionnaireBlockId);
        setLoading(false);
        return;
      }

      await startSession(resumed.session_id);
      await loadNextTrial(resumed.session_id);
    } catch {
      setError(localizedError('error.startSession'));
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
    resumeBannerKey,
    savedFeedback,
    setStage,
    loadPublicRunInfo,
    beginSession,
    continueResumedSession,
    submitCurrentTrial,
    submitQuestionnaire,
    submitFinalSession,
    retryCurrent: () =>
      sessionId ? loadNextTrial(sessionId) : setError(localizedError('error.missingSessionStateShort')),
  };
}
