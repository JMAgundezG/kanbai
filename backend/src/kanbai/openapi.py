"""Export the OpenAPI schema to backend/openapi.json.

The file is committed so that a contract change shows up in code review, and the
frontend can run `npm run gen:api` without a running server.

The schema is built from the field defaults only: the environment, the .env file
and any secrets directory are removed as sources, so the committed contract is
byte-identical on every machine instead of picking up whatever KANBAI_* variables
the person running the exporter happens to have set.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from kanbai.core.config import Settings

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "openapi.json"

# Never connected to: the schema does not depend on the database.
_PLACEHOLDER_DSN = PostgresDsn("postgresql+psycopg://kanbai:kanbai@localhost:5432/kanbai")


class SchemaSettings(Settings):
    """Settings for the exported contract: defaults plus what is passed here."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)


def build_schema() -> dict[str, Any]:
    from kanbai.main import create_app

    return create_app(SchemaSettings(database_url=_PLACEHOLDER_DSN)).openapi()


def export(path: Path = OPENAPI_PATH) -> Path:
    payload = json.dumps(build_schema(), indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(payload + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(f"OpenAPI escrito en {export()}")
