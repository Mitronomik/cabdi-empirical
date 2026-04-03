# PR-001 — Docs and prompt normalization

## Goal

Normalize the repository prompt/docs workflow without changing runtime behavior.

## Why

The repository already contains:
- repo-wide rules in `AGENTS.md`
- human-pilot standing instructions in `docs/pilot/codex_master_prompt.md`
- pilot operational docs in `docs/pilot/`

This PR should make the prompt workflow explicit and reduce duplication.

## In scope

- add `docs/pilot/pr_roadmap.md`
- add `docs/pilot/prs/`
- add the first PR prompt files
- reconcile any duplicate root-level `codex_master_prompt.md` with `docs/pilot/codex_master_prompt.md`
- keep one canonical master prompt location
- patch `README.md` only if needed to mention the docs workflow

## Out of scope

- no API changes
- no DB changes
- no UI changes
- no policy logic changes
- no deployment changes

## Acceptance criteria

- one canonical human-pilot master prompt location
- roadmap file exists
- PR prompt folder exists
- no broken references in `AGENTS.md` or `README.md`
- no runtime files changed except docs references if strictly needed
