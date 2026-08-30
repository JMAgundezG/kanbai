"""Application settings, loaded once from the environment."""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every knob the application reads from its environment.

    `extra="forbid"` turns a misspelled key in .env into a startup failure instead
    of a value that is silently ignored (a stray KANBAI_* environment variable is
    never read at all), and `database_url` has no default so an unconfigured
    deployment fails immediately rather than on its first query.
    """

    model_config = SettingsConfigDict(
        env_prefix="KANBAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    app_name: str = "kanbai"
    environment: Literal["local", "test", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_url: PostgresDsn
    db_echo: bool = False

    api_v1_prefix: str = "/api/v1"
    cors_origins: list[AnyHttpUrl] = [AnyHttpUrl("http://localhost:5173")]


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance, injected with `Depends(get_settings)`."""
    return Settings()
