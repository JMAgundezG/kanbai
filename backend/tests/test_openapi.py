"""The committed contract must match the code that produces it — everywhere."""

import json

import pytest

from kanbai.openapi import OPENAPI_PATH, build_schema


def test_openapi_json_esta_sincronizado() -> None:
    assert OPENAPI_PATH.exists(), "Falta backend/openapi.json: ejecuta `uv run poe openapi`."

    committed = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

    assert committed == build_schema(), (
        "openapi.json está desactualizado respecto al código. "
        "Ejecuta `uv run poe openapi` y vuelve a generar los tipos del frontend."
    )


def test_el_esquema_no_depende_del_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two settings feed the schema (app_name and api_v1_prefix). If the exporter
    read them from the environment, whoever ran it would commit a different
    contract, and the frontend would generate types for endpoints that do not
    exist."""
    monkeypatch.setenv("KANBAI_APP_NAME", "otro-nombre")
    monkeypatch.setenv("KANBAI_API_V1_PREFIX", "/api/v2")

    schema = build_schema()

    assert schema["info"]["title"] == "kanbai"
    assert "/api/v1/health/ready" in schema["paths"]
