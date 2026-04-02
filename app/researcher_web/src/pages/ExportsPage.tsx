import React, { useState } from 'react'
import { apiGet } from '../lib/api'

export function ExportsPage() {
  const [runId, setRunId] = useState('')
  const [response, setResponse] = useState('')

  async function load() {
    const out = await apiGet(`/admin/api/v1/runs/${runId}/exports`)
    setResponse(JSON.stringify(out, null, 2))
  }

  return (
    <section>
      <h2>Exports</h2>
      <input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="run_id" />
      <button onClick={load}>Load Exports</button>
      <pre>{response}</pre>
    </section>
  )
}
