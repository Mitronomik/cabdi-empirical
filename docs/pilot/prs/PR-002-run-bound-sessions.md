# PR-002 — Bind participant sessions to concrete runs

## Goal

Make participant sessions belong to a concrete run instead of floating loosely at experiment level.

## Why

The intended researcher flow is:
stimulus bank -> create run -> sessions -> diagnostics -> exports.

The current behavior allows ambiguity between uploaded banks, runs, and participant sessions.

## In scope

- require run binding in participant session creation
- preserve existing logging/export flow
- adapt session lifecycle to run-based state
- update tests
- update docs where needed

## Out of scope

- auth
- Postgres migration
- deployment hardening
- UI redesign beyond what is strictly needed to support run-bound sessions

## Acceptance criteria

- session cannot be created without run context
- run/session relationship is explicit in persistence
- dry-run remains functional or is updated coherently
- exports still work
- relevant tests pass
