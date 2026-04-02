"""Stimulus bank validation utilities for pilot mode."""

from __future__ import annotations

import json
from pathlib import Path

from packages.shared_types.pilot_types import StimulusItem


def load_stimulus_bank(path: str | Path) -> list[StimulusItem]:
    """Load JSONL stimulus bank and validate every row against StimulusItem."""
    items: list[StimulusItem] = []
    seen_ids: set[str] = set()

    for line_no, raw_line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at line {line_no}") from exc

        item = StimulusItem.from_dict(payload)
        if item.stimulus_id in seen_ids:
            raise ValueError(f"Duplicate stimulus_id detected: {item.stimulus_id}")
        seen_ids.add(item.stimulus_id)
        items.append(item)

    if not items:
        raise ValueError("Stimulus bank is empty")
    return items
