# Codex Master Prompt for Human-Pilot Mode

This document defines the standing implementation constitution for extending `cabdi-empirical` from a synthetic scaffold into a dual-mode research platform with human-pilot mode.

This file is complementary to the repository root `AGENTS.md`.
When working on human-pilot mode, follow both:
1. `AGENTS.md`
2. `docs/pilot/codex_master_prompt.md`

If there is a conflict:
- direct user/system instructions override both,
- `AGENTS.md` remains the repo-wide operating contract,
- this document gives the detailed implementation program for human-pilot mode.

Work in the existing repository `cabdi-empirical`.

You are extending an existing synthetic empirical validation scaffold into a dual-mode research platform:
1) existing synthetic mode (already present in the repo),
2) new human-pilot mode for a minimal real-task CABDI toy pilot.

IMPORTANT OPERATING RULES
- Do NOT replace or break the current synthetic scaffold.
- Do NOT create a separate standalone project unless direct repo constraints make it impossible.
- Reuse and extend existing structures wherever reasonable.
- Keep the current repo’s scientific tone and scope discipline:
  - this repo supports / narrows / falsifies selected CABDI claims,
  - it does NOT establish whole-framework real-world validation,
  - it does NOT validate latent-state semantics or physiology-dependent claims.
- Treat the participant-facing pilot as behavior-first and limited to adjudicable observable targets.

==================================================
1. REPO REALITY AND GOAL
==================================================

The current repository already contains a synthetic scaffold with directories such as:
- artifacts/
- docs/paper/
- experiments/
- legacy_seed/
- models/
- policies/
- reports/
- sim/
- tests/

The synthetic scaffold operationalizes reduced slow routing model families F_d, compares CABDI-style routing against matched-budget baselines, and supports theorem-facing filtering and synthetic falsification.

Your goal is to add a new “human-pilot mode” inside this SAME repository, not as a disconnected project.

The target outcome is an MVP service that can:
- run a minimal toy real-task pilot with human participants,
- use the same policy families:
  - static_help
  - monotone_help
  - cabdi_lite
- assign pre-render risk buckets,
- render policy-specific assistance contracts,
- log event-level and trial-level data,
- export data for mixed-effects-ready analysis,
- generate pilot diagnostics and summary reports,
- remain fully compatible in spirit with the existing synthetic scaffold.

==================================================
2. HIGH-LEVEL ARCHITECTURE
==================================================

Implement a dual-mode architecture:

A. Synthetic mode (already exists)
- state comes from sim/
- policy logic comes from policies/
- writes existing artifact/report outputs

B. Human-pilot mode (new)
- state proxy comes from pre-render trial context (stimulus + recent history),
- uses the SAME policy engine family,
- serves participant UI,
- writes structured event logs and trial summary logs,
- runs an analysis pipeline to derive observable anchors.

CRITICAL INVARIANT:
Policy logic MUST NOT live in the frontend.
The frontend only renders a structured PolicyDecision returned by backend/policy runtime.

==================================================
3. TARGET FILE/FOLDER ADDITIONS
==================================================

Prefer the following structure unless the repo already has a clearly better local convention:

app/
  participant_api/
  participant_web/
  researcher_api/
  researcher_web/

pilot/
  configs/
  stimuli/
  sessions/
  exports/

analysis/
  pilot/

packages/
  shared_types/
  logging_schema/

Within existing top-level directories:
- extend policies/ with pilot-specific contracts and rules
- extend tests/ with pilot-specific tests
- add docs/pilot/ with short operational docs

Do NOT delete or rename existing synthetic directories unless absolutely necessary.

==================================================
4. CORE DOMAIN MODELS
==================================================

Add typed schemas/models for the following domain objects.

4.1 StimulusItem
Fields:
- stimulus_id: str
- task_family: str
- content_type: "text" | "image" | "vignette"
- payload: dict
- true_label: str
- difficulty_prior: "low" | "medium" | "high"
- model_prediction: str
- model_confidence: "low" | "medium" | "high"
- model_correct: bool
- eligible_sets: list[str]
- notes: optional str

4.2 ExperimentConfig
Fields:
- experiment_id: str
- task_family: str
- n_blocks: int
- trials_per_block: int
- practice_trials: int
- conditions: list[str]
- block_order_strategy: str
- budget_matching_mode: str
- risk_proxy_mode: str
- self_confidence_scale: str
- block_questionnaires: list[str]

4.3 ParticipantSession
Fields:
- session_id
- participant_id
- experiment_id
- assigned_order
- stimulus_set_map
- current_block_index
- current_trial_index
- status
- started_at
- completed_at
- device_info

4.4 TrialContext
Fields:
- session_id
- participant_id
- condition
- block_id
- trial_id
- stimulus: StimulusItem
- recent_history: dict
- pre_render_features: dict

4.5 RiskBucket
Values:
- low
- moderate
- extreme

4.6 PolicyDecision
Fields:
- condition
- risk_bucket
- show_prediction: bool
- show_confidence: bool
- show_rationale: "none" | "inline" | "on_click"
- show_evidence: bool
- verification_mode: "none" | "soft_prompt" | "forced_checkbox" | "forced_second_look"
- compression_mode: "none" | "medium" | "high"
- max_extra_steps: int
- ui_help_level: str
- ui_verification_level: str
- budget_signature: dict

4.7 TrialEventLog
Event-level log with:
- event_id
- session_id
- block_id
- trial_id
- timestamp
- event_type
- payload

Supported event types:
- trial_started
- assistance_rendered
- reason_clicked
- evidence_opened
- verification_checked
- response_selected
- confidence_submitted
- trial_completed

4.8 TrialSummaryLog
Compact per-trial summary with all essential fields for later analysis:
- participant/session/experiment identifiers
- condition
- stimulus_id
- task_family
- true_label
- human_response
- correct_or_not
- model_prediction
- model_confidence
- model_correct_or_not
- risk_bucket
- shown_help_level
- shown_verification_level
- shown_components
- accepted_model_advice
- overrode_model
- verification_required
- verification_completed
- reason_clicked
- evidence_opened
- reaction_time_ms
- self_confidence

==================================================
5. POLICY ENGINE REQUIREMENTS
==================================================

Add pilot policy logic inside policies/, not inside UI code.

Create:
- policies/contracts.py
- policies/pilot_rules.py
- policies/budget_checks.py

5.1 Conditions

A. static_help
Same assistance across all risk buckets:
- show_prediction = True
- show_confidence = True
- show_rationale = "inline"
- show_evidence = False
- verification_mode = "none"
- compression_mode = "none"
- max_extra_steps = 0

B. monotone_help
low:
- prediction only
- no rationale
- no evidence
- no verification

moderate:
- prediction
- confidence
- inline rationale
- no evidence
- no forced verification

extreme:
- prediction
- confidence
- inline rationale
- evidence available
- soft verify prompt
- no compression

C. cabdi_lite
low:
- prediction only or minimal panel
- no rationale
- no evidence
- no verification
- minimal friction

moderate:
- prediction
- confidence
- inline rationale
- soft verification prompt
- no evidence
- no compression

extreme:
- prediction
- confidence
- rationale only on click
- evidence hidden by default
- forced verification
- compressed assistance
- at most one extra interaction step
- emphasis on reducing blind acceptance, not on increasing assistance volume

5.2 Pre-render risk assignment v1
Risk bucket MUST be computed before assistance is rendered.
Do not recompute risk within the same trial.

Inputs:
- model_confidence
- difficulty_prior
- recent_error_count_last_3
- recent_blind_accept_count_last_3
- recent_latency_z_bucket

Simple rule:
low:
- high model confidence
- low/medium difficulty
- no recent instability spike

moderate:
- medium model confidence OR
- high difficulty OR
- one instability marker

extreme:
- low model confidence OR
- high difficulty + recent blind acceptance OR
- two or more instability markers

5.3 Budget matching discipline
Implement explicit budget diagnostics.

Track at least:
A. Assistance display budget:
- number of shown components
- total text tokens shown
- evidence availability count

B. Interaction budget:
- max extra steps per trial
- mean extra steps per block
- verification actions per block

Support config tolerances such as:
- text_budget_tolerance_pct
- interaction_budget_tolerance_pct
- hard_max_extra_steps_per_trial

The system must generate warnings if budget matching tolerance is violated.

==================================================
6. API REQUIREMENTS
==================================================

Use FastAPI for the MVP backend unless strong repo constraints force a different local solution.
Keep the MVP simple. No complex auth.

Implement participant-facing API endpoints roughly like:

GET /health

POST /api/v1/sessions
POST /api/v1/sessions/{session_id}/start
GET /api/v1/sessions/{session_id}/next-trial
POST /api/v1/sessions/{session_id}/trials/{trial_id}/submit
POST /api/v1/sessions/{session_id}/blocks/{block_id}/questionnaire
GET /api/v1/exports/sessions/{session_id}

Implement researcher/admin endpoints roughly like:

POST /admin/api/v1/stimuli/upload
POST /admin/api/v1/runs
GET /admin/api/v1/runs/{run_id}/diagnostics
GET /admin/api/v1/runs/{run_id}/exports

Use persistence suitable for MVP (e.g. SQLite or simple local DB layer), but structure code so it can later move to Postgres cleanly.

==================================================
7. PARTICIPANT WEB REQUIREMENTS
==================================================

Implement a minimal participant web app.

Required screens:
- consent
- instructions
- practice block (6 trials)
- main trial screen
- post-trial micro-transition
- block-end burden/trust/usefulness items
- completion/debrief screen

UI requirements:
- neutral, readable, no visual overload
- identical structural layout across conditions
- assistance panel varies only by PolicyDecision
- frontend must not contain policy logic
- clear participant copy stating that AI can be wrong and should not be followed blindly

Trial screen should include:
- progress indicator
- stimulus card
- AI assistance panel
- decision buttons
- optional reason/evidence controls as permitted by PolicyDecision
- self-confidence response after answer

==================================================
8. RESEARCHER WEB REQUIREMENTS
==================================================

Implement a minimal researcher/admin web app.

Required functions:
- upload stimuli
- validate stimulus schema
- create experiment run
- inspect session completion counts
- inspect basic diagnostics
- export artifacts

Diagnostics should include:
- completion count
- abandonment count
- model-wrong trial distribution
- budget matching diagnostics
- missing-field warnings
- block-order distribution
- reveal/verification usage rates

==================================================
9. ANALYSIS PIPELINE
==================================================

Add analysis code under analysis/pilot/.

Required scripts/modules:
- derive_metrics.py
- exclusions.py
- summaries.py
- mixed_effects_ready.py
- report_builder.py

Derived metrics must include:
- utility_accuracy
- commission_error_rate
- correct_override_rate
- appropriate_reliance_proxy
- mean_rt
- verification_burden
- reason_click_rate
- switch_burden_proxy
- self_reported_burden

Exclusion flags must include at least:
- too_fast_responder
- missing_confidence_reports
- incomplete_session
- repeated_same_response_pattern
- logging_corruption_flag

Output artifacts must include at least:
- trial_level.csv
- participant_summary.csv
- mixed_effects_ready.csv
- pilot_summary.md

==================================================
10. DRY-RUN / QA MODE
==================================================

Add a dry-run harness for human-pilot mode without real participants.

Create a script such as:
- experiments/run_toy_pilot_dry_run.py

It should:
- simulate fake participant sessions,
- walk through the participant flow,
- generate event logs and trial summaries,
- run the pilot analysis pipeline,
- write artifacts and a markdown report.

This dry-run mode is important because the repo already has synthetic infrastructure.
Reuse scaffold logic wherever sensible for QA, but keep the human-pilot dry-run clearly separate from theorem-facing synthetic validation outputs.

==================================================
11. CONFIGS
==================================================

Add configs under pilot/configs/:
- default_experiment.yaml
- policy_conditions.yaml
- latin_square_orders.yaml

Add a small demo stimulus bank under:
- pilot/stimuli/scam_not_scam_demo.jsonl

The app should be runnable with a single default toy task family from config.

==================================================
12. TESTS
==================================================

Add tests under tests/:

- test_pilot_policy_rules.py
- test_pilot_budget_matching.py
- test_pilot_logging_schema.py
- test_pilot_randomization.py
- test_pilot_analysis_pipeline.py

These tests must verify:
- static_help invariance
- monotone escalation
- cabdi extreme differs from monotone extreme
- no within-trial risk recomputation
- budget tolerance checks
- log schema completeness
- Latin square assignment
- balanced stimuli/model-wrong distribution
- derived metric correctness
- export file structure

Do not skip tests.

==================================================
13. README / DOCS PATCH
==================================================

Update README.md to add a “Human-pilot mode” section stating that:
- the repo now also supports a minimal real-task toy pilot service,
- it uses the same policy families as the synthetic scaffold,
- it remains behavior-first,
- it logs adjudicable observable targets,
- it does NOT validate latent-state semantics or physiology-dependent claims.

Also add short docs:
- docs/pilot/admin_guide.md
- docs/pilot/participant_flow.md

==================================================
14. IMPLEMENTATION ORDER
==================================================

Do NOT implement everything chaotically.
Work in the following sequence:

PHASE 1
- shared schemas
- configs
- policy runtime
- budget diagnostics
- tests for these

PHASE 2
- FastAPI backend
- session lifecycle
- persistence
- API tests

PHASE 3
- participant web
- researcher web
- UI integration

PHASE 4
- analysis pipeline
- exports
- pilot summary report

PHASE 5
- dry-run harness
- README/docs patch
- cleanup and final tests

==================================================
15. OUTPUT FORMAT FOR YOUR WORK
==================================================

As you work:
- first inspect the repo and adapt paths if needed,
- then propose a concrete implementation plan aligned with the repo’s actual structure,
- then implement in small coherent slices,
- after each major slice, summarize what changed,
- run tests where relevant,
- do not leave the repo in a half-broken state,
- prefer minimal coherent changes over speculative architecture.

If a requested file path or structure conflicts with the actual repo organization, preserve repo coherence and explain the adapted placement in your summary.

The final result should be an MVP research service that is understandable, testable, and aligned with CABDI’s epistemic limits.
