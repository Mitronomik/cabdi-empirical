# PR-006 — Public participant boundary cleanup

## Goal

Finish normalizing participant API usage so the web client contract is canonical under `/api/v1/public/...`.

## Canonical participant public contract

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

## Transitional legacy alias policy

Legacy `/api/v1/sessions/...` aliases remain temporarily available for compatibility, but are explicitly transitional:

- marked `deprecated: true` in OpenAPI;
- emit deprecation headers in responses;
- documented as non-canonical for participant web.

## Invariants maintained

- run-bound entry (`run_slug`) for create/resume;
- snapshot-based run/session lifecycle;
- explicit final-submit gating semantics;
- backend-owned policy/risk decisions (no frontend decision computation);
- public participant and researcher/admin surfaces remain separated.
