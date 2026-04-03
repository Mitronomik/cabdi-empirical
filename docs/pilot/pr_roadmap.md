# CABDI Pilot PR Roadmap

This file defines the minimal implementation slices for the human-pilot evolution of `cabdi-empirical`.

## Principles

- Keep the repository dual-mode: synthetic scaffold + human-pilot mode.
- Do not break or replace the synthetic scaffold.
- Reuse one shared policy engine where practical.
- Keep participant-facing pilot behavior-first and limited to adjudicable observable targets.
- Do not overclaim pilot outputs as whole-framework validation.

## PR-001
Normalize prompt/docs structure and add PR workflow docs.

## PR-002
Bind participant sessions to concrete runs instead of loose experiment-level flow.

## PR-003
Add public run entry by `run_slug` and make participant session creation run-bound.

## PR-004
Add resume flow, progress persistence UX, and explicit final submit.

## PR-005
Improve researcher/admin workflow:
- visible stimulus library
- upload feedback
- run builder
- session monitor
- diagnostics visibility

## PR-006
Add researcher/admin protection and deployment hardening:
- private researcher surface
- auth
- Postgres preparation
- VPS-ready configuration
