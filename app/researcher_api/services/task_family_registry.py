"""Task-family registry for stimulus validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskFamilySpec:
    """Validation contract for one task family."""

    task_family: str
    label_space: frozenset[str]


_REGISTRY: dict[str, TaskFamilySpec] = {
    "scam_detection": TaskFamilySpec(task_family="scam_detection", label_space=frozenset({"scam", "not_scam"})),
    "scam_not_scam": TaskFamilySpec(task_family="scam_not_scam", label_space=frozenset({"scam", "not_scam"})),
}
_LEGACY_UI_DEFAULT_TASK_FAMILIES = frozenset({"scam_detection", "scam_not_scam"})


def list_supported_task_families() -> frozenset[str]:
    """Return registered task-family names."""

    return frozenset(_REGISTRY.keys())


def get_task_family_spec(task_family: str) -> TaskFamilySpec | None:
    """Return task-family spec, if registered."""

    return _REGISTRY.get(task_family)


def has_builtin_ui_defaults(task_family: str) -> bool:
    """Return whether participant UI has built-in fallback response options."""

    return task_family in _LEGACY_UI_DEFAULT_TASK_FAMILIES


def register_task_family(*, task_family: str, label_space: set[str] | frozenset[str]) -> None:
    """Register or replace a task-family validation spec."""

    normalized_labels = frozenset(label.strip() for label in label_space if label.strip())
    if not task_family.strip():
        raise ValueError("task_family must be non-empty")
    if not normalized_labels:
        raise ValueError("label_space must contain at least one non-empty label")
    _REGISTRY[task_family.strip()] = TaskFamilySpec(task_family=task_family.strip(), label_space=normalized_labels)
