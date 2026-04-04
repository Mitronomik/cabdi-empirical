from __future__ import annotations

from pathlib import Path


SERVICE_MODULES = (
    Path("app/participant_api/services"),
    Path("app/researcher_api/services"),
)


def test_service_layers_do_not_import_sqlite_helpers() -> None:
    forbidden_snippets = (
        "from app.participant_api.persistence.sqlite_store import",
        "import app.participant_api.persistence.sqlite_store",
    )
    for module_dir in SERVICE_MODULES:
        for py_file in module_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for snippet in forbidden_snippets:
                assert snippet not in content, f"sqlite persistence leakage in service layer: {py_file}"
