const BASE = import.meta.env.VITE_RESEARCHER_API_BASE ?? 'http://localhost:8001'

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function createRun(payload: Record<string, unknown>) {
  const res = await fetch(`${BASE}/admin/api/v1/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function uploadStimuli(form: FormData) {
  const res = await fetch(`${BASE}/admin/api/v1/stimuli/upload`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
