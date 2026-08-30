"""Boards and membership: creation, listing, permissions, and the invariant that
membership does not branch on actor kind."""

import asyncio
import uuid
from http import HTTPStatus
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from kanbai.models.actor import Person
from kanbai.models.board_member import BoardMember
from kanbai.repositories import actors as actors_repository
from kanbai.repositories import board_members as board_members_repository
from kanbai.repositories import boards as boards_repository
from kanbai.services import agents as agents_service
from kanbai.services import auth as auth_service
from kanbai.services import boards as boards_service

OWNER_PASSWORD = "correcto-caballo-batería-grapa"


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
    member exactly like a person does — membership never branches on actor kind.
    The agent's owner is `owner` itself, so the permission-ceiling check TASK-09
    adds to `add_member` (see services/boards.py) is trivially satisfied: `owner`
    is already this board's owner, at least as high a role as the "member" the
    agent is granted here."""
    agent = await agents_service.create_agent(
        db_session, actor=owner, display_name="Bot de pruebas", description=None
    )

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


# --- concurrencia real: el lock del techo de permisos de un agente --------------
#
# Igual que las pruebas de concurrencia de test_cards.py: sesiones y conexiones
# propias, con COMMIT de verdad — la fixture `db_session` mete cada test en un
# SAVEPOINT que siempre se revierte, así que sobre ella no hay concurrencia real
# que demostrar.
#
# Comprobar solo que `add_member` "se queda esperando" no basta: el INSERT final
# en `board_members` ya bloquea contra el lock de fila del tablero porque
# Postgres exige un `FOR KEY SHARE` implícito sobre la fila padre para
# comprobar la FK — eso pasaría igual sin `lock_board_for_update` en absoluto.
# Lo que hay que demostrar es que la *lectura* del techo de permisos (antes de
# ese INSERT) ve el estado posterior al commit de la otra transacción, no una
# foto anterior — que es exactamente lo que evita el hallazgo de la code
# review. Por eso la otra transacción, mientras sostiene el lock, deja sin
# comprometer justo la fila de `board_members` que decide si la comprobación
# del techo pasa o falla: si `add_member` lee antes de esperar el lock, ve la
# ausencia de esa fila y rechaza al momento; si espera el lock (el fix), ve la
# fila ya comprometida y acepta.


async def _cleanup_board_and_actors(
    engine: AsyncEngine, *, board_id: uuid.UUID, actor_ids: list[uuid.UUID]
) -> None:
    async with engine.connect() as cleanup:
        await cleanup.execute(text("DELETE FROM boards WHERE id = :id"), {"id": board_id})
        for actor_id in actor_ids:
            await cleanup.execute(text("DELETE FROM actors WHERE id = :id"), {"id": actor_id})
        await cleanup.commit()


async def test_anadir_agente_lee_el_techo_de_permisos_tras_esperar_el_lock(
    engine: AsyncEngine,
) -> None:
    """El hallazgo de la code review de TASK-09, demostrado con una
    interleaving real: si `add_member` no esperase el lock del tablero antes de
    comprobar el techo de permisos del agente, esta prueba fallaría — no por
    quedarse "colgada" sin más, sino porque devolvería el `ConflictError`
    equivocado casi al instante, en vez de esperar y aceptar."""
    unique_owner_email = f"lock-owner-{uuid.uuid4().hex}@example.com"
    unique_ceiling_email = f"lock-ceiling-{uuid.uuid4().hex}@example.com"
    async with AsyncSession(engine, expire_on_commit=False) as setup_session:
        owner = await auth_service.create_person(
            setup_session,
            email=unique_owner_email,
            password="cualquier-cosa-larga-1234",
            display_name="Owner del lock",
        )
        ceiling_person = await auth_service.create_person(
            setup_session,
            email=unique_ceiling_email,
            password="cualquier-cosa-larga-1234",
            display_name="Persona techo",
        )
        board, _ = await boards_service.create_board(setup_session, actor=owner, name="Con lock")
        agent = await agents_service.create_agent(
            setup_session, actor=ceiling_person, display_name="Bot del lock", description=None
        )
        owner_id, ceiling_id, agent_id, board_id = owner.id, ceiling_person.id, agent.id, board.id

    try:
        holder_session = AsyncSession(engine, expire_on_commit=False)
        await boards_repository.lock_board_for_update(holder_session, board_id)
        # Sin comprometer: `ceiling_person` aún no es visible como miembro para
        # ninguna otra transacción hasta que `holder_session` haga commit.
        await board_members_repository.add_member(
            holder_session, board_id=board_id, actor_id=ceiling_id, role="member"
        )
        try:

            async def _add_agent_in_own_session() -> BoardMember:
                async with AsyncSession(engine, expire_on_commit=False) as session:
                    actor = await actors_repository.get_actor_by_id(session, owner_id)
                    assert actor is not None
                    return await boards_service.add_member(
                        session,
                        actor=actor,
                        board_id=board_id,
                        new_actor_id=agent_id,
                        role="member",
                    )

            racing_task = asyncio.ensure_future(_add_agent_in_own_session())
            _, pending = await asyncio.wait({racing_task}, timeout=0.5)
            assert racing_task in pending, (
                "add_member no debería resolver el techo de permisos del agente "
                "mientras la membresía de su persona propietaria sigue sin "
                "comprometerse en otra transacción"
            )

            await holder_session.commit()
            member = await asyncio.wait_for(racing_task, timeout=5)
            assert member.actor_id == agent_id
        finally:
            await holder_session.close()
    finally:
        await _cleanup_board_and_actors(
            engine, board_id=board_id, actor_ids=[owner_id, ceiling_id, agent_id]
        )
