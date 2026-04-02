import React, { useState } from 'react'
import { Nav, type PageKey } from './components/Nav'
import { DiagnosticsPage } from './pages/DiagnosticsPage'
import { ExportsPage } from './pages/ExportsPage'
import { RunBuilderPage } from './pages/RunBuilderPage'
import { SessionMonitorPage } from './pages/SessionMonitorPage'
import { StimulusUploadPage } from './pages/StimulusUploadPage'

function App() {
  const [page, setPage] = useState<PageKey>('upload')

  return (
    <main>
      <h1>CABDI Researcher Admin (MVP)</h1>
      <Nav page={page} setPage={setPage} />
      {page === 'upload' && <StimulusUploadPage />}
      {page === 'run' && <RunBuilderPage />}
      {page === 'sessions' && <SessionMonitorPage />}
      {page === 'diagnostics' && <DiagnosticsPage />}
      {page === 'exports' && <ExportsPage />}
    </main>
  )
}

export default App
