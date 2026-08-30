"""Agent management: sign-up, listing, detail, and API key issuance/revocation.

Every route here requires the caller to be a person (`services/agents.py`
enforces it) — the one deliberate exception to CLAUDE.md § 0's "no branching on
actor kind" in the whole API, because this whole router *is* that boundary.
Everywhere else (`boards`, `columns`, `cards`) an agent authenticates with its
key and is authorized exactly like a person, through `CurrentActor` alone.
"""

import uuid
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter

from kanbai.api.deps import CurrentActor, PaginationDep, SessionDep
from kanbai.schemas.agent import AgentCreate, AgentRead, ApiKeyCreated, ApiKeyRead
from kanbai.schemas.pagination import Page
from kanbai.services import agents as agents_service

router = APIRouter(prefix="/agents", tags=["agents"])

_ONLY_PERSON: dict[int | str, dict[str, Any]] = {
    HTTPStatus.FORBIDDEN: {"description": "Solo una persona puede gestionar agentes."}
}
_NOT_OWNED: dict[int | str, dict[str, Any]] = {
    **_ONLY_PERSON,
    HTTPStatus.NOT_FOUND: {"description": "El agente (o la API key) no existe o no te pertenece."},
}


@router.post(
    "",
    response_model=AgentRead,
    status_code=HTTPStatus.CREATED,
    summary="Da de alta un agente propio",
    responses=_ONLY_PERSON,
)
async def create_agent(payload: AgentCreate, session: SessionDep, actor: CurrentActor) -> AgentRead:
    agent = await agents_service.create_agent(
        session, actor=actor, display_name=payload.display_name, description=payload.description
    )
    return AgentRead.model_validate(agent)


@router.get(
    "",
    response_model=Page[AgentRead],
    summary="Lista los agentes propios",
    responses=_ONLY_PERSON,
)
async def list_agents(
    session: SessionDep, actor: CurrentActor, pagination: PaginationDep
) -> Page[AgentRead]:
    agents, total = await agents_service.list_agents(
        session, actor=actor, limit=pagination.limit, offset=pagination.offset
    )
    return Page[AgentRead](
        items=[AgentRead.model_validate(agent) for agent in agents],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get(
    "/{agent_id}",
    response_model=AgentRead,
    summary="Obtiene un agente propio por id",
    responses=_NOT_OWNED,
)
async def get_agent(agent_id: uuid.UUID, session: SessionDep, actor: CurrentActor) -> AgentRead:
    agent = await agents_service.get_agent(session, actor=actor, agent_id=agent_id)
    return AgentRead.model_validate(agent)


@router.post(
    "/{agent_id}/keys",
    response_model=ApiKeyCreated,
    status_code=HTTPStatus.CREATED,
    summary="Emite una API key nueva para el agente (el valor en claro solo se ve aquí)",
    responses=_NOT_OWNED,
)
async def create_api_key(
    agent_id: uuid.UUID, session: SessionDep, actor: CurrentActor
) -> ApiKeyCreated:
    key, full_key = await agents_service.create_api_key(session, actor=actor, agent_id=agent_id)
    return ApiKeyCreated(
        id=key.id,
        prefix=key.prefix,
        created_at=key.created_at,
        revoked_at=key.revoked_at,
        api_key=full_key,
    )


@router.get(
    "/{agent_id}/keys",
    response_model=Page[ApiKeyRead],
    summary="Lista las API keys del agente (sin el secreto)",
    responses=_NOT_OWNED,
)
async def list_api_keys(
    agent_id: uuid.UUID, session: SessionDep, actor: CurrentActor, pagination: PaginationDep
) -> Page[ApiKeyRead]:
    keys, total = await agents_service.list_api_keys(
        session, actor=actor, agent_id=agent_id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[ApiKeyRead](
        items=[ApiKeyRead.model_validate(key) for key in keys],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/{agent_id}/keys/{key_id}/revoke",
    response_model=ApiKeyRead,
    summary="Revoca una API key (idempotente)",
    responses=_NOT_OWNED,
)
async def revoke_api_key(
    agent_id: uuid.UUID, key_id: uuid.UUID, session: SessionDep, actor: CurrentActor
) -> ApiKeyRead:
    key = await agents_service.revoke_api_key(
        session, actor=actor, agent_id=agent_id, key_id=key_id
    )
    return ApiKeyRead.model_validate(key)
