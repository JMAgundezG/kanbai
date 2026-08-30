"""Health endpoints: the vertical slice through router → service → repository → DB."""

from http import HTTPStatus

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from kanbai.db.session import get_session


class UnreachableSession:
    """Stands in for a session whose database has gone away."""

    async def execute(self, *args: object, **kwargs: object) -> object:
        raise SQLAlchemyError("connection to server at 127.0.0.1 failed")


async def test_liveness_devuelve_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


async def test_readiness_consulta_la_base_de_datos(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_readiness_devuelve_503_cuando_la_base_de_datos_falla(
    app: FastAPI, client: AsyncClient
) -> None:
    app.dependency_overrides[get_session] = lambda: UnreachableSession()

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {"status": "error", "database": "error"}
    # The database error belongs in the log, not in the response body.
    assert "127.0.0.1" not in response.text


async def test_liveness_sigue_ok_sin_base_de_datos(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_session] = lambda: UnreachableSession()

    response = await client.get("/health")

    assert response.status_code == HTTPStatus.OK


async def test_ruta_inexistente_devuelve_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/no-existe")

    assert response.status_code == HTTPStatus.NOT_FOUND
