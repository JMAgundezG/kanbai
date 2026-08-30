"""How the app is wired: settings must not leak in from the environment."""

from fastapi import FastAPI

from kanbai.core.config import Settings
from kanbai.main import create_app


def test_la_app_usa_los_settings_que_recibe(settings: Settings) -> None:
    """Everything derived from settings hangs off app.state, so a request can never
    reach an engine built from a different configuration."""
    app = create_app(settings)

    expected_database = (settings.database_url.path or "").lstrip("/")

    assert app.state.settings is settings
    assert app.state.engine.url.database == expected_database


def test_produccion_no_publica_la_documentacion(settings: Settings) -> None:
    production = settings.model_copy(update={"environment": "production"})

    app: FastAPI = create_app(production)

    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
