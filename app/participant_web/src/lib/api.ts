import type { QuestionnairePayload, TrialPayload } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

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
  progress?: {
    completed_trials: number;
    total_trials: number;
    current_ordinal: number;
  };
}

export async function createSession(
  runSlug: string,
  language: "en" | "ru",
  resumeToken?: string | null,
): Promise<{ session_id: string; status: string; entry_mode: 'created' | 'resumed'; resume_token: string }> {
  return request(`/api/v1/public/runs/${encodeURIComponent(runSlug)}/sessions`, {
    method: 'POST',
    body: JSON.stringify({ language, resume_token: resumeToken ?? undefined }),
  });
}

export async function fetchResumeInfo(runSlug: string, resumeToken: string): Promise<{
  resume_status: 'resumable' | 'finalized' | 'invalid' | 'not_resumable';
  session_id?: string;
  session_status?: string;
  current_stage?: string;
  current_block_index?: number;
  current_trial_index?: number;
}> {
  return request(`/api/v1/public/runs/${encodeURIComponent(runSlug)}/resume-info`, {
    method: 'POST',
    body: JSON.stringify({ resume_token: resumeToken }),
  });
}

export async function resumeSession(runSlug: string, resumeToken: string): Promise<{
  resume_status: 'resumable' | 'finalized' | 'invalid' | 'not_resumable';
  session_id?: string;
  session_status?: string;
  current_stage?: string;
  current_block_index?: number;
  current_trial_index?: number;
}> {
  return request(`/api/v1/public/runs/${encodeURIComponent(runSlug)}/resume`, {
    method: 'POST',
    body: JSON.stringify({ resume_token: resumeToken }),
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
  return request(`/api/v1/public/sessions/${sessionId}/start`, { method: 'POST' });
}

export async function fetchSessionProgress(sessionId: string): Promise<{
  session_id: string;
  status: string;
  current_stage: string;
  current_block_index: number;
  current_trial_index: number;
}> {
  return request(`/api/v1/public/sessions/${sessionId}/progress`);
}

export async function fetchNextTrial(sessionId: string): Promise<TrialPayload | NextTrialResponseCompleted> {
  return request(`/api/v1/public/sessions/${sessionId}/next-trial`);
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
): Promise<{ trial_id: string; status: string; session_completed?: boolean; saved_ack?: { saved: boolean; saved_at?: string } }> {
  return request(`/api/v1/public/sessions/${sessionId}/trials/${trialId}/submit`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function submitBlockQuestionnaire(
  sessionId: string,
  blockId: string,
  payload: QuestionnairePayload,
): Promise<{ block_id: string; status: string; session_completed?: boolean; saved_ack?: { saved: boolean; saved_at?: string } }> {
  return request(`/api/v1/public/sessions/${sessionId}/blocks/${blockId}/questionnaire`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function finalSubmitSession(
  sessionId: string,
): Promise<{ session_id: string; status: string; final_submit: string; already_finalized: boolean }> {
  return request(`/api/v1/public/sessions/${sessionId}/final-submit`, {
    method: 'POST',
  });
}
