# PR-005 — Public participant API normalization

## Goal

Make participant-facing endpoints canonical under explicit public namespaces that are run-scoped at entry and session-scoped during lifecycle execution.

## Canonical public routes

- `GET /api/v1/public/runs/{run_slug}`
- `POST /api/v1/public/runs/{run_slug}/sessions`
- `POST /api/v1/public/runs/{run_slug}/resume-info`
- `POST /api/v1/public/runs/{run_slug}/resume`
- `POST /api/v1/public/sessions/{session_id}/start`
- `GET /api/v1/public/sessions/{session_id}/progress`
- `GET /api/v1/public/sessions/{session_id}/next-trial`
- `POST /api/v1/public/sessions/{session_id}/trials/{trial_id}/submit`
- `POST /api/v1/public/sessions/{session_id}/blocks/{block_id}/questionnaire`
- `POST /api/v1/public/sessions/{session_id}/final-submit`

## Compatibility

Legacy `/api/v1/sessions/...` aliases are intentionally retained for compatibility, but no longer treated as canonical in participant web clients.

## Invariants kept

- Session creation/resume remains run-bound.
- Session lifecycle remains snapshot-based and final-submit-gated.
- Policy decisions and risk bucket logic remain backend/runtime responsibilities.
- Public participant routes remain separated from researcher/admin routes.
