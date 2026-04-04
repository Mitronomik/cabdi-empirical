import type { QuestionnairePayload, TrialPayload } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw { status: res.status, detail: body?.detail ?? body, raw: body };
  }

  return (await res.json()) as T;
}

export interface NextTrialResponseCompleted {
  status: 'awaiting_final_submit' | 'finalized' | 'completed';
  no_more_trials?: boolean;
  session_id?: string;
}

export async function createSession(
  participantId: string,
  runSlug: string,
  language: "en" | "ru",
  resumeToken?: string | null,
): Promise<{ session_id: string; status: string; entry_mode: 'created' | 'resumed'; resume_token: string }> {
  return request('/api/v1/sessions', {
    method: 'POST',
    body: JSON.stringify({ participant_id: participantId, run_slug: runSlug, language, resume_token: resumeToken ?? undefined }),
  });
}

export async function fetchResumeInfo(runSlug: string, resumeToken: string): Promise<{
  resume_status: 'resumable' | 'finalized' | 'invalid' | 'not_resumable';
  session_id?: string;
  session_status?: string;
}> {
  return request('/api/v1/sessions/resume-info', {
    method: 'POST',
    body: JSON.stringify({ run_slug: runSlug, resume_token: resumeToken }),
  });
}

export async function fetchPublicRun(runSlug: string): Promise<{
  run_slug: string;
  public_title: string;
  public_description?: string;
  launchable: boolean;
  run_status: string;
}> {
  return request(`/api/v1/public/runs/${encodeURIComponent(runSlug)}`);
}

export async function startSession(sessionId: string): Promise<{ session_id: string; status: string }> {
  return request(`/api/v1/sessions/${sessionId}/start`, { method: 'POST' });
}

export async function fetchNextTrial(sessionId: string): Promise<TrialPayload | NextTrialResponseCompleted> {
  return request(`/api/v1/sessions/${sessionId}/next-trial`);
}

export async function submitTrial(
  sessionId: string,
  trialId: string,
  payload: {
    human_response: string;
    reaction_time_ms: number;
    self_confidence: number;
    reason_clicked: boolean;
    evidence_opened: boolean;
    verification_completed: boolean;
    event_trace?: Array<{ event_type: string; payload: Record<string, unknown> }>;
  },
): Promise<{ trial_id: string; status: string; session_completed?: boolean }> {
  return request(`/api/v1/sessions/${sessionId}/trials/${trialId}/submit`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function submitBlockQuestionnaire(
  sessionId: string,
  blockId: string,
  payload: QuestionnairePayload,
): Promise<{ block_id: string; status: string; session_completed?: boolean }> {
  return request(`/api/v1/sessions/${sessionId}/blocks/${blockId}/questionnaire`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function finalSubmitSession(
  sessionId: string,
): Promise<{ session_id: string; status: string; final_submit: string; already_finalized: boolean }> {
  return request(`/api/v1/sessions/${sessionId}/final-submit`, {
    method: 'POST',
  });
}
