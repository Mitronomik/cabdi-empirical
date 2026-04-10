const BASE = import.meta.env.VITE_RESEARCHER_API_BASE ?? ''

async function parseError(res: Response): Promise<string> {
  const text = await res.text()
  if (!text) return `HTTP ${res.status}`
  try {
    const parsed = JSON.parse(text) as { detail?: string }
    if (parsed.detail) return parsed.detail
  } catch {
    // noop: preserve raw text fallback
  }
  return text
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function createRun(payload: Record<string, unknown>) {
  const res = await fetch(`${BASE}/admin/api/v1/runs`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function apiPost<T>(path: string, payload?: Record<string, unknown>): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: payload ? JSON.stringify(payload) : undefined,
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function uploadStimuli(form: FormData) {
  const res = await fetch(`${BASE}/admin/api/v1/stimuli/upload`, { method: 'POST', credentials: 'include', body: form })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export function login(username: string, password: string) {
  return apiPost<{ ok: boolean; user: { user_id: string; username: string; is_admin: boolean } }>(
    '/admin/api/v1/auth/login',
    { username, password },
  )
}

export function logout() {
  return apiPost<{ ok: boolean }>('/admin/api/v1/auth/logout')
}

export function getCurrentUser() {
  return apiGet<{ authenticated: boolean; user: { user_id: string; username: string; is_admin: boolean } }>(
    '/admin/api/v1/auth/me',
  )
}

export function listStimuli() {
  return apiGet<Array<Record<string, unknown>>>('/admin/api/v1/stimuli')
}

export function listRuns() {
  return apiGet<Array<Record<string, unknown>>>('/admin/api/v1/runs')
}

export function getDashboard(focusRunId?: string) {
  const query = focusRunId ? `?focus_run_id=${encodeURIComponent(focusRunId)}` : ''
  return apiGet<Record<string, unknown>>(`/admin/api/v1/dashboard${query}`)
}

export function getRun(runId: string) {
  return apiGet<Record<string, unknown>>(`/admin/api/v1/runs/${runId}`)
}

export function activateRun(runId: string) {
  return apiPost<Record<string, unknown>>(`/admin/api/v1/runs/${runId}/activate`)
}

export function pauseRun(runId: string) {
  return apiPost<Record<string, unknown>>(`/admin/api/v1/runs/${runId}/pause`)
}

export function closeRun(runId: string) {
  return apiPost<Record<string, unknown>>(`/admin/api/v1/runs/${runId}/close`, { confirm_run_id: runId })
}

export function getRunBuilderDefaults() {
  return apiGet<Record<string, unknown>>('/admin/api/v1/runs/defaults')
}

export function getRunSessions(runId: string) {
  return apiGet<Record<string, unknown>>(`/admin/api/v1/runs/${runId}/sessions`)
}

export function getRunDiagnostics(runId: string) {
  return apiGet<Record<string, unknown>>(`/admin/api/v1/runs/${runId}/diagnostics`)
}

export function getRunExports(runId: string) {
  return apiGet<Record<string, unknown>>(`/admin/api/v1/runs/${runId}/exports`)
}

export async function downloadRunExportArtifact(runId: string, artifactType: string): Promise<Blob> {
  const res = await fetch(`${BASE}/admin/api/v1/runs/${runId}/exports/artifacts/${artifactType}`, {
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.blob()
}
