"""Settings must fail loudly instead of starting up half-configured."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from kanbai.core.config import Settings


def test_settings_falla_sin_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KANBAI_DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as excinfo:
        # _env_file=None ignores the developer's .env so the check is deterministic.
        Settings(_env_file=None)

    assert "database_url" in str(excinfo.value)


def test_settings_rechaza_claves_desconocidas_en_el_env(tmp_path: Path) -> None:
    """A typo in .env must fail at startup instead of being silently ignored.

    Note the boundary: `extra="forbid"` rejects unknown keys coming from the .env
    file and from explicit arguments, but a stray KANBAI_* environment variable is
    never read at all — pydantic-settings only looks up the names it knows.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KANBAI_DATABASE_URL=postgresql+psycopg://u:p@localhost:5432/db\nKANBAI_TYPO_OPTION=1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=env_file)

    assert "typo_option" in str(excinfo.value).lower()
