"""Boards and membership: creation, listing, permissions, and the invariant that
membership does not branch on actor kind."""

from http import HTTPStatus
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.models.actor import Actor, Person
from kanbai.services import auth as auth_service

OWNER_PASSWORD = "correcto-caballo-batería-grapa"


class _AgentDouble(Actor):
    """Test-only stand-in for the `Agent` subclass TASK-09 will add.

    SQLAlchemy's joined-table inheritance refuses to *read back* a row whose
    discriminator has no registered subclass — `Actor(kind="agent")` alone raises
    on the next `select(Actor)`. Declaring this here (single-table: no
    `__tablename__`, so it adds no column and no table) registers the
    "agent" polymorphic identity for the duration of the test suite, letting the
    real repository/service code paths run against an actual second actor kind
    without adding an `Agent` model to production code ahead of TASK-09's scope.
    """

    __mapper_args__ = {"polymorphic_identity": "agent"}  # noqa: RUF012


@pytest.fixture
async def owner(db_session: AsyncSession) -> Person:
    return await auth_service.create_person(
        db_session, email="owner@example.com", password=OWNER_PASSWORD, display_name="Owner"
    )


@pytest.fixture
async def other_person(db_session: AsyncSession) -> Person:
    return await auth_service.create_person(
        db_session,
        email="otro@example.com",
        password="otra-contraseña-cualquiera",
        display_name="Otra",
    )


async def _login(client: AsyncClient, email: str, password: str) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == HTTPStatus.OK


async def _create_board(client: AsyncClient, name: str = "Tablero de prueba") -> dict[str, Any]:
    response = await client.post("/api/v1/boards", json={"name": name})
    assert response.status_code == HTTPStatus.CREATED
    result: dict[str, Any] = response.json()
    return result


# --- creación ------------------------------------------------------------------


async def test_crear_tablero_deja_al_actor_como_owner(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)

    board = await _create_board(client, "Mi primer tablero")

    assert board["name"] == "Mi primer tablero"
    assert board["role"] == "owner"
    assert "id" in board
    assert "created_at" in board


async def test_crear_tablero_sin_sesion_devuelve_401(client: AsyncClient) -> None:
    response = await client.post("/api/v1/boards", json={"name": "Sin sesión"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_crear_tablero_nombre_vacio_devuelve_422(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)

    response = await client.post("/api/v1/boards", json={"name": ""})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- listado y paginación --------------------------------------------------------


async def test_listar_tableros_devuelve_solo_los_propios(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    my_board = await _create_board(client, "Tablero de owner")

    await _login(client, other_person.email, "otra-contraseña-cualquiera")
    await _create_board(client, "Tablero de otra persona")

    await _login(client, owner.email, OWNER_PASSWORD)
    response = await client.get("/api/v1/boards")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [my_board["id"]]
    assert body["page"] == 1
    assert body["size"] == 20


async def test_listar_tableros_respeta_paginacion(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    for i in range(3):
        await _create_board(client, f"Tablero {i}")

    response = await client.get("/api/v1/boards", params={"page": 1, "size": 2})

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["size"] == 2


async def test_listar_tableros_size_por_encima_del_maximo_devuelve_422(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)

    response = await client.get("/api/v1/boards", params={"size": 101})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- lectura y edición de un tablero ---------------------------------------------


async def test_obtener_tablero_propio_devuelve_detalle_con_rol(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    response = await client.get(f"/api/v1/boards/{board['id']}")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["role"] == "owner"


async def test_obtener_tablero_ajeno_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    await _login(client, other_person.email, "otra-contraseña-cualquiera")
    response = await client.get(f"/api/v1/boards/{board['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_renombrar_tablero_como_owner(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client, "Nombre viejo")

    response = await client.patch(f"/api/v1/boards/{board['id']}", json={"name": "Nombre nuevo"})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "Nombre nuevo"


async def test_renombrar_tablero_ajeno_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    await _login(client, other_person.email, "otra-contraseña-cualquiera")
    response = await client.patch(f"/api/v1/boards/{board['id']}", json={"name": "Intento ajeno"})

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_renombrar_tablero_como_member_no_owner_devuelve_403(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )

    await _login(client, other_person.email, "otra-contraseña-cualquiera")
    response = await client.patch(
        f"/api/v1/boards/{board['id']}", json={"name": "No debería poder"}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


async def test_borrar_tablero_como_owner(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    response = await client.delete(f"/api/v1/boards/{board['id']}")
    get_response = await client.get(f"/api/v1/boards/{board['id']}")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert get_response.status_code == HTTPStatus.NOT_FOUND


async def test_borrar_tablero_como_member_no_owner_devuelve_403(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )

    await _login(client, other_person.email, "otra-contraseña-cualquiera")
    response = await client.delete(f"/api/v1/boards/{board['id']}")

    assert response.status_code == HTTPStatus.FORBIDDEN


# --- membresía ------------------------------------------------------------------


async def test_anadir_miembro_persona(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    response = await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )

    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert body["role"] == "member"
    assert body["actor"]["kind"] == "person"
    assert body["actor"]["id"] == str(other_person.id)


async def test_anadir_miembro_agente_funciona_igual_que_persona(
    client: AsyncClient, owner: Person, db_session: AsyncSession
) -> None:
    """The invariant from CLAUDE.md §0: an actor of kind "agent" becomes a board
    member exactly like a person does — membership never branches on actor kind."""
    agent = _AgentDouble(display_name="Bot de pruebas")
    db_session.add(agent)
    await db_session.flush()
    await db_session.commit()

    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    response = await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(agent.id), "role": "member"},
    )

    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert body["actor"]["kind"] == "agent"
    assert body["actor"]["id"] == str(agent.id)


async def test_anadir_miembro_duplicado_devuelve_409(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    payload = {"actor_id": str(other_person.id), "role": "member"}
    await client.post(f"/api/v1/boards/{board['id']}/members", json=payload)

    response = await client.post(f"/api/v1/boards/{board['id']}/members", json=payload)

    assert response.status_code == HTTPStatus.CONFLICT


async def test_anadir_miembro_actor_inexistente_devuelve_404(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    response = await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": "00000000-0000-0000-0000-000000000000", "role": "member"},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_anadir_miembro_como_no_owner_devuelve_403(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )

    await _login(client, other_person.email, "otra-contraseña-cualquiera")
    response = await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


async def test_listar_miembros_incluye_al_owner(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    response = await client.get(f"/api/v1/boards/{board['id']}/members")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["role"] == "owner"
    assert body["items"][0]["actor"]["id"] == str(owner.id)


async def test_listar_miembros_tablero_ajeno_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    await _login(client, other_person.email, "otra-contraseña-cualquiera")
    response = await client.get(f"/api/v1/boards/{board['id']}/members")

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_quitar_miembro_como_owner(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    add_response = await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )
    member_id = add_response.json()["id"]

    response = await client.delete(f"/api/v1/boards/{board['id']}/members/{member_id}")
    members_response = await client.get(f"/api/v1/boards/{board['id']}/members")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert members_response.json()["total"] == 1


async def test_quitar_unico_owner_devuelve_409(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    members = (await client.get(f"/api/v1/boards/{board['id']}/members")).json()["items"]
    owner_member_id = next(m["id"] for m in members if m["role"] == "owner")

    response = await client.delete(f"/api/v1/boards/{board['id']}/members/{owner_member_id}")

    assert response.status_code == HTTPStatus.CONFLICT


async def test_owner_puede_quitarse_si_hay_otro_owner(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "owner"},
    )
    members = (await client.get(f"/api/v1/boards/{board['id']}/members")).json()["items"]
    owner_member_id = next(m["id"] for m in members if m["actor"]["id"] == str(owner.id))

    response = await client.delete(f"/api/v1/boards/{board['id']}/members/{owner_member_id}")

    assert response.status_code == HTTPStatus.NO_CONTENT


async def test_miembro_no_owner_puede_quitarse_a_si_mismo(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    add_response = await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )
    member_id = add_response.json()["id"]

    await _login(client, other_person.email, "otra-contraseña-cualquiera")
    response = await client.delete(f"/api/v1/boards/{board['id']}/members/{member_id}")

    assert response.status_code == HTTPStatus.NO_CONTENT


async def test_quitar_a_otro_miembro_sin_ser_owner_devuelve_403(
    client: AsyncClient, owner: Person, other_person: Person, db_session: AsyncSession
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )
    members = (await client.get(f"/api/v1/boards/{board['id']}/members")).json()["items"]
    owner_member_id = next(m["id"] for m in members if m["actor"]["id"] == str(owner.id))

    await _login(client, other_person.email, "otra-contraseña-cualquiera")
    response = await client.delete(f"/api/v1/boards/{board['id']}/members/{owner_member_id}")

    assert response.status_code == HTTPStatus.FORBIDDEN


async def test_quitar_miembro_inexistente_devuelve_404(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    response = await client.delete(
        f"/api/v1/boards/{board['id']}/members/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
