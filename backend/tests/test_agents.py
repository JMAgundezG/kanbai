"""Agents: sign-up, API key issuance and revocation, and the two invariants this
whole task exists to prove — an agent authenticated by its key is authorized on
boards/columns/cards exactly like a person, and it never outranks the person
that created it (CLAUDE.md §0)."""

from http import HTTPStatus
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.models.actor import Person
from kanbai.models.agent import AgentApiKey
from kanbai.services import agents as agents_service
from kanbai.services import auth as auth_service

OWNER_PASSWORD = "correcto-caballo-batería-grapa"
OTHER_PASSWORD = "otra-contraseña-cualquiera"


@pytest.fixture
async def owner(db_session: AsyncSession) -> Person:
    return await auth_service.create_person(
        db_session, email="owner@example.com", password=OWNER_PASSWORD, display_name="Owner"
    )


@pytest.fixture
async def other_person(db_session: AsyncSession) -> Person:
    return await auth_service.create_person(
        db_session, email="otra@example.com", password=OTHER_PASSWORD, display_name="Otra"
    )


async def _login(client: AsyncClient, email: str, password: str) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == HTTPStatus.OK


async def _create_board(client: AsyncClient, name: str = "Tablero de prueba") -> dict[str, Any]:
    response = await client.post("/api/v1/boards", json={"name": name})
    assert response.status_code == HTTPStatus.CREATED
    result: dict[str, Any] = response.json()
    return result


async def _bare_client(app: FastAPI) -> AsyncClient:
    """A client with no cookies at all — used for every call that must
    authenticate purely via `Authorization: Bearer`. Reusing the logged-in
    `client` fixture for this would be self-defeating: `get_current_actor` tries
    the cookie before the header, so a leftover session cookie would silently
    resolve the request as the person, not the agent."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# --- alta de agentes -------------------------------------------------------------


async def test_crear_agente_devuelve_201_y_queda_ligado_al_creador(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)

    response = await client.post(
        "/api/v1/agents", json={"display_name": "Bot", "description": "Un agente de prueba"}
    )

    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert body["kind"] == "agent"
    assert body["display_name"] == "Bot"
    assert body["description"] == "Un agente de prueba"
    assert body["owner_person_id"] == str(owner.id)


async def test_crear_agente_sin_sesion_devuelve_401(client: AsyncClient) -> None:
    response = await client.post("/api/v1/agents", json={"display_name": "Bot"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_agente_no_puede_crear_agentes_devuelve_403(
    app: FastAPI, client: AsyncClient, owner: Person, db_session: AsyncSession
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    agent = await agents_service.create_agent(
        db_session, actor=owner, display_name="Bot", description=None
    )
    _, full_key = await agents_service.create_api_key(db_session, actor=owner, agent_id=agent.id)

    async with await _bare_client(app) as agent_client:
        response = await agent_client.post(
            "/api/v1/agents",
            json={"display_name": "Bot hijo"},
            headers={"Authorization": f"Bearer {full_key}"},
        )

    assert response.status_code == HTTPStatus.FORBIDDEN


async def test_persona_no_ve_agentes_de_otra_persona(
    client: AsyncClient, owner: Person, other_person: Person, db_session: AsyncSession
) -> None:
    agent = await agents_service.create_agent(
        db_session, actor=owner, display_name="Bot", description=None
    )

    await _login(client, other_person.email, OTHER_PASSWORD)

    list_response = await client.get("/api/v1/agents")
    assert list_response.json()["items"] == []

    detail_response = await client.get(f"/api/v1/agents/{agent.id}")
    assert detail_response.status_code == HTTPStatus.NOT_FOUND


# --- API keys ----------------------------------------------------------------


async def test_emitir_api_key_devuelve_el_valor_en_claro_una_sola_vez(
    client: AsyncClient, owner: Person, db_session: AsyncSession
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    agent = await agents_service.create_agent(
        db_session, actor=owner, display_name="Bot", description=None
    )

    create_response = await client.post(f"/api/v1/agents/{agent.id}/keys")

    assert create_response.status_code == HTTPStatus.CREATED
    created_body = create_response.json()
    assert created_body["api_key"].startswith("kanbai_agent_")
    assert "revoked_at" in created_body and created_body["revoked_at"] is None

    list_response = await client.get(f"/api/v1/agents/{agent.id}/keys")
    assert list_response.status_code == HTTPStatus.OK
    listed_keys = list_response.json()["items"]
    assert len(listed_keys) == 1
    assert "api_key" not in listed_keys[0]
    assert listed_keys[0]["prefix"] == created_body["prefix"]


async def test_key_en_claro_no_se_guarda_en_base_de_datos(
    client: AsyncClient, owner: Person, db_session: AsyncSession
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    agent = await agents_service.create_agent(
        db_session, actor=owner, display_name="Bot", description=None
    )

    key, full_key = await agents_service.create_api_key(db_session, actor=owner, agent_id=agent.id)

    assert key.secret_hash != full_key
    assert full_key not in key.secret_hash
    assert isinstance(key, AgentApiKey)


async def test_key_revocada_devuelve_401(
    app: FastAPI, client: AsyncClient, owner: Person, db_session: AsyncSession
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    agent = await agents_service.create_agent(
        db_session, actor=owner, display_name="Bot", description=None
    )
    key, full_key = await agents_service.create_api_key(db_session, actor=owner, agent_id=agent.id)
    await agents_service.revoke_api_key(db_session, actor=owner, agent_id=agent.id, key_id=key.id)

    async with await _bare_client(app) as agent_client:
        response = await agent_client.get(
            "/api/v1/boards", headers={"Authorization": f"Bearer {full_key}"}
        )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_key_inexistente_devuelve_401(app: FastAPI) -> None:
    async with await _bare_client(app) as agent_client:
        response = await agent_client.get(
            "/api/v1/boards",
            headers={"Authorization": "Bearer kanbai_agent_no-existe.tampoco-existe"},
        )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_key_malformada_devuelve_401(app: FastAPI) -> None:
    async with await _bare_client(app) as agent_client:
        response = await agent_client.get(
            "/api/v1/boards", headers={"Authorization": "Bearer no-tiene-el-prefijo-correcto"}
        )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_revocar_key_de_otro_agente_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person, db_session: AsyncSession
) -> None:
    agent = await agents_service.create_agent(
        db_session, actor=owner, display_name="Bot", description=None
    )
    key, _ = await agents_service.create_api_key(db_session, actor=owner, agent_id=agent.id)

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.post(f"/api/v1/agents/{agent.id}/keys/{key.id}/revoke")

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_revocar_key_es_idempotente(
    client: AsyncClient, owner: Person, db_session: AsyncSession
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    agent = await agents_service.create_agent(
        db_session, actor=owner, display_name="Bot", description=None
    )
    key, _ = await agents_service.create_api_key(db_session, actor=owner, agent_id=agent.id)

    first = await client.post(f"/api/v1/agents/{agent.id}/keys/{key.id}/revoke")
    second = await client.post(f"/api/v1/agents/{agent.id}/keys/{key.id}/revoke")

    assert first.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.OK
    assert first.json()["revoked_at"] == second.json()["revoked_at"]


# --- el agente operando sobre el dominio, igual que una persona ------------------


async def test_agente_opera_tableros_columnas_y_tarjetas_igual_que_una_persona(
    app: FastAPI, client: AsyncClient, owner: Person, db_session: AsyncSession
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    agent = await agents_service.create_agent(
        db_session, actor=owner, display_name="Bot", description=None
    )
    _, full_key = await agents_service.create_api_key(db_session, actor=owner, agent_id=agent.id)
    add_member_response = await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(agent.id), "role": "member"},
    )
    assert add_member_response.status_code == HTTPStatus.CREATED

    async with await _bare_client(app) as agent_client:
        headers = {"Authorization": f"Bearer {full_key}"}

        boards_response = await agent_client.get("/api/v1/boards", headers=headers)
        assert boards_response.status_code == HTTPStatus.OK
        assert [b["id"] for b in boards_response.json()["items"]] == [board["id"]]

        columns_response = await agent_client.get(
            f"/api/v1/boards/{board['id']}/columns", headers=headers
        )
        assert columns_response.status_code == HTTPStatus.OK
        column_id = columns_response.json()["items"][0]["id"]

        create_card_response = await agent_client.post(
            f"/api/v1/boards/{board['id']}/cards",
            json={"column_id": column_id, "title": "Tarjeta del agente"},
            headers=headers,
        )
        assert create_card_response.status_code == HTTPStatus.CREATED
        card = create_card_response.json()
        assert card["created_by_actor_id"] == str(agent.id)

        move_response = await agent_client.post(
            f"/api/v1/boards/{board['id']}/cards/{card['id']}/move",
            json={"column_id": column_id, "position": 0},
            headers=headers,
        )
        assert move_response.status_code == HTTPStatus.OK


async def test_agente_no_miembro_de_un_tablero_recibe_404(
    app: FastAPI, client: AsyncClient, owner: Person, other_person: Person, db_session: AsyncSession
) -> None:
    await _login(client, other_person.email, OTHER_PASSWORD)
    board = await _create_board(client, "Tablero ajeno")

    agent = await agents_service.create_agent(
        db_session, actor=owner, display_name="Bot", description=None
    )
    _, full_key = await agents_service.create_api_key(db_session, actor=owner, agent_id=agent.id)

    async with await _bare_client(app) as agent_client:
        response = await agent_client.get(
            f"/api/v1/boards/{board['id']}", headers={"Authorization": f"Bearer {full_key}"}
        )

    assert response.status_code == HTTPStatus.NOT_FOUND


# --- un agente nunca supera los permisos de su persona propietaria --------------


async def test_anadir_agente_cuya_persona_no_es_miembro_devuelve_409(
    client: AsyncClient, owner: Person, other_person: Person, db_session: AsyncSession
) -> None:
    """The central proof of CLAUDE.md §0's "an agent never outranks the person
    that created it": a board owned by a third party rejects an agent whose
    owning person is not (yet) a member — and accepts it the moment she is."""
    agent = await agents_service.create_agent(
        db_session, actor=other_person, display_name="Bot ajeno", description=None
    )

    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    rejected = await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(agent.id), "role": "member"},
    )
    assert rejected.status_code == HTTPStatus.CONFLICT

    add_owner_first = await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )
    assert add_owner_first.status_code == HTTPStatus.CREATED

    accepted = await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(agent.id), "role": "member"},
    )
    assert accepted.status_code == HTTPStatus.CREATED


async def test_anadir_agente_como_owner_cuando_su_persona_es_solo_member_devuelve_409(
    client: AsyncClient, owner: Person, other_person: Person, db_session: AsyncSession
) -> None:
    agent = await agents_service.create_agent(
        db_session, actor=other_person, display_name="Bot ajeno", description=None
    )

    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )

    response = await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(agent.id), "role": "owner"},
    )

    assert response.status_code == HTTPStatus.CONFLICT


async def test_crear_tablero_como_agente_anade_tambien_a_su_persona_propietaria(
    app: FastAPI, client: AsyncClient, owner: Person, db_session: AsyncSession
) -> None:
    agent = await agents_service.create_agent(
        db_session, actor=owner, display_name="Bot", description=None
    )
    _, full_key = await agents_service.create_api_key(db_session, actor=owner, agent_id=agent.id)

    async with await _bare_client(app) as agent_client:
        create_response = await agent_client.post(
            "/api/v1/boards",
            json={"name": "Tablero del agente"},
            headers={"Authorization": f"Bearer {full_key}"},
        )
    assert create_response.status_code == HTTPStatus.CREATED
    board = create_response.json()

    await _login(client, owner.email, OWNER_PASSWORD)
    owner_view = await client.get(f"/api/v1/boards/{board['id']}")

    assert owner_view.status_code == HTTPStatus.OK
    assert owner_view.json()["role"] == "owner"
