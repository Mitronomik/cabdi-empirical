from __future__ import annotations

from packages.shared_types.pilot_types import RiskBucket
from policies.budget_checks import (
    compare_budget_to_reference,
    serialize_budget_traces,
    summarize_budgets_by_condition,
    summarize_interaction_by_block,
)
from policies.contracts import BudgetTrace


def _sample_traces() -> list[BudgetTrace]:
    return [
        BudgetTrace(
            condition="static_help",
            risk_bucket=RiskBucket.LOW,
            shown_components_count=2,
            shown_text_tokens=40,
            evidence_available=0,
            max_extra_steps=0,
            realized_extra_steps=0,
            verification_actions=0,
            block_id="b1",
        ),
        BudgetTrace(
            condition="static_help",
            risk_bucket=RiskBucket.MODERATE,
            shown_components_count=2,
            shown_text_tokens=40,
            evidence_available=0,
            max_extra_steps=0,
            realized_extra_steps=0,
            verification_actions=0,
            block_id="b1",
        ),
        BudgetTrace(
            condition="cabdi_lite",
            risk_bucket=RiskBucket.EXTREME,
            shown_components_count=3,
            shown_text_tokens=60,
            evidence_available=0,
            max_extra_steps=1,
            realized_extra_steps=1,
            verification_actions=1,
            block_id="b1",
        ),
    ]


def test_budget_summaries_are_produced():
    traces = _sample_traces()
    by_condition = summarize_budgets_by_condition(traces)
    by_block = summarize_interaction_by_block(traces)

    assert set(by_condition.keys()) == {"static_help", "cabdi_lite"}
    assert by_condition["static_help"]["mean_text_tokens_shown"] == 40
    assert by_condition["cabdi_lite"]["max_extra_steps_per_trial"] == 1

    assert set(by_block.keys()) == {"b1"}
    assert by_block["b1"]["verification_actions"] == 1


def test_budget_tolerance_and_hard_cap_checks_emit_flags():
    observed = {
        "static_help": {
            "mean_text_tokens_shown": 60.0,
            "mean_realized_extra_steps": 0.6,
            "max_extra_steps_per_trial": 2.0,
        }
    }
    reference = {
        "static_help": {
            "mean_text_tokens_shown": 40.0,
            "mean_realized_extra_steps": 0.2,
            "max_extra_steps_per_trial": 0.0,
        }
    }

    flags = compare_budget_to_reference(
        observed,
        reference,
        text_budget_tolerance_pct=10.0,
        interaction_budget_tolerance_pct=20.0,
        hard_max_extra_steps_per_trial=1,
    )
    kinds = {f["kind"] for f in flags}

    assert "text_tolerance_exceeded" in kinds
    assert "interaction_tolerance_exceeded" in kinds
    assert "hard_cap_exceeded" in kinds


def test_budget_trace_serialization_has_string_risk_bucket():
    rows = serialize_budget_traces(_sample_traces())
    assert rows[0]["risk_bucket"] == "low"
    assert rows[-1]["risk_bucket"] == "extreme"
