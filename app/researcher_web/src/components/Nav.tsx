import React from 'react'

export type PageKey = 'upload' | 'run' | 'sessions' | 'diagnostics' | 'exports'

export function Nav({ page, setPage }: { page: PageKey; setPage: (p: PageKey) => void }) {
  const pages: PageKey[] = ['upload', 'run', 'sessions', 'diagnostics', 'exports']
  return (
    <nav>
      {pages.map((p) => (
        <button key={p} onClick={() => setPage(p)} disabled={p === page} style={{ marginRight: 8 }}>
          {p}
        </button>
      ))}
    </nav>
  )
}
