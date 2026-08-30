"""Person authentication: login, logout, /me and the guarantees around them."""

from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.core.exceptions import ConflictError
from kanbai.models.actor import Person
from kanbai.services import auth as auth_service

TEST_EMAIL = "ada@example.com"
TEST_PASSWORD = "correcto-caballo-batería-grapa"
TEST_DISPLAY_NAME = "Ada Lovelace"


@pytest.fixture
async def person(db_session: AsyncSession) -> Person:
    return await auth_service.create_person(
        db_session,
        email=TEST_EMAIL,
        password=TEST_PASSWORD,
        display_name=TEST_DISPLAY_NAME,
    )


async def test_login_correcto_devuelve_sesion_y_200(client: AsyncClient, person: Person) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["kind"] == "person"
    assert body["display_name"] == TEST_DISPLAY_NAME
    assert body["id"] == str(person.id)
    assert "kanbai_session" in response.cookies


async def test_login_normaliza_mayusculas_en_el_email(client: AsyncClient, person: Person) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL.upper(), "password": TEST_PASSWORD},
    )

    assert response.status_code == HTTPStatus.OK


async def test_login_password_incorrecta_devuelve_401(client: AsyncClient, person: Person) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": "no-es-esta"}
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert "kanbai_session" not in response.cookies


async def test_login_email_inexistente_da_el_mismo_401_que_password_incorrecta(
    client: AsyncClient, person: Person
) -> None:
    wrong_password = await client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": "no-es-esta"}
    )
    unknown_email = await client.post(
        "/api/v1/auth/login",
        json={"email": "no-existe@example.com", "password": "lo-que-sea"},
    )

    assert unknown_email.status_code == HTTPStatus.UNAUTHORIZED
    # Same status and same body: the response never reveals whether the email
    # exists in the system.
    assert unknown_email.json() == wrong_password.json()


async def test_login_no_expone_la_contrasena_en_la_respuesta(
    client: AsyncClient, person: Person
) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )

    assert TEST_PASSWORD not in response.text
    assert "password" not in response.json()


async def test_me_sin_sesion_devuelve_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_me_con_sesion_devuelve_el_actor(client: AsyncClient, person: Person) -> None:
    await client.post("/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["id"] == str(person.id)
    assert body["kind"] == "person"


async def test_me_con_cookie_invalida_devuelve_401(client: AsyncClient) -> None:
    client.cookies.set("kanbai_session", "un-token-que-no-existe")

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_logout_invalida_la_sesion(client: AsyncClient, person: Person) -> None:
    await client.post("/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})

    logout_response = await client.post("/api/v1/auth/logout")
    me_response = await client.get("/api/v1/auth/me")

    assert logout_response.status_code == HTTPStatus.NO_CONTENT
    assert me_response.status_code == HTTPStatus.UNAUTHORIZED


async def test_logout_sin_sesion_devuelve_204(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == HTTPStatus.NO_CONTENT


async def test_create_person_email_duplicado_da_conflicto(
    db_session: AsyncSession, person: Person
) -> None:
    with pytest.raises(ConflictError):
        await auth_service.create_person(
            db_session,
            email=TEST_EMAIL,
            password="otra-contraseña-cualquiera",
            display_name="Otro nombre",
        )
