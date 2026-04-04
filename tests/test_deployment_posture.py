from __future__ import annotations

import pytest

from app.participant_api.main import create_app as create_participant_app
from app.researcher_api.main import create_app as create_researcher_app


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [
        "PILOT_ENV",
        "PILOT_DB_URL",
        "PILOT_DB_PATH",
        "PILOT_PARTICIPANT_CORS_ORIGINS",
        "PILOT_RESEARCHER_CORS_ORIGINS",
        "PILOT_RESEARCHER_SESSION_SECRET",
        "PILOT_RESEARCHER_PASSWORD",
        "PILOT_RESEARCHER_COOKIE_SECURE",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_participant_staging_requires_explicit_cors_and_postgres_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("PILOT_ENV", "staging")
    with pytest.raises(RuntimeError, match="PILOT_PARTICIPANT_CORS_ORIGINS"):
        create_participant_app(str(tmp_path / "pilot.sqlite3"))

    monkeypatch.setenv("PILOT_PARTICIPANT_CORS_ORIGINS", "https://participant.example.org")
    with pytest.raises(RuntimeError, match="PILOT_DB_URL"):
        create_participant_app(str(tmp_path / "pilot.sqlite3"))


def test_researcher_staging_requires_explicit_secure_config(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("PILOT_ENV", "staging")
    monkeypatch.setenv("PILOT_RESEARCHER_CORS_ORIGINS", "https://researcher.example.org")
    monkeypatch.setenv("PILOT_DB_URL", "postgresql://staging-user:staging-pass@db:5432/cabdi")
    monkeypatch.setenv("PILOT_RESEARCHER_PASSWORD", "strong-pass")

    with pytest.raises(RuntimeError, match="PILOT_RESEARCHER_SESSION_SECRET"):
        create_researcher_app(str(tmp_path / "pilot.sqlite3"))

    monkeypatch.setenv("PILOT_RESEARCHER_SESSION_SECRET", "a" * 48)
    app = create_researcher_app(str(tmp_path / "pilot.sqlite3"))
    assert app.state.researcher_cookie_secure is True


def test_researcher_cookie_secure_defaults_false_in_local(tmp_path) -> None:
    app = create_researcher_app(str(tmp_path / "pilot.sqlite3"))
    assert app.state.researcher_cookie_secure is False


def test_participant_cors_origins_are_environment_driven(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("PILOT_PARTICIPANT_CORS_ORIGINS", "https://participant.example.org,https://public.example.org")
    app = create_participant_app(str(tmp_path / "pilot.sqlite3"))
    cors_middleware = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert cors_middleware.kwargs["allow_origins"] == [
        "https://participant.example.org",
        "https://public.example.org",
    ]
