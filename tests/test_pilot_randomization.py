from __future__ import annotations

from app.participant_api.services.randomization_service import assign_order_id


def test_assigned_order_is_reproducible_for_same_participant():
    first = assign_order_id("p_001", "pilot_scam_not_scam_v1")
    second = assign_order_id("p_001", "pilot_scam_not_scam_v1")
    assert first == second


def test_assigned_order_is_valid_latin_square_row():
    order_id, order = assign_order_id("p_002", "pilot_scam_not_scam_v1")
    assert order_id.startswith("order_")
    assert set(order) == {"static_help", "monotone_help", "cabdi_lite"}
