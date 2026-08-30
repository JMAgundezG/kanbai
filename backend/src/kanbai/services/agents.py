"""Agent lifecycle and API key issuance/verification.

`_require_person` is the one deliberate exception to CLAUDE.md § 0's "no
branching on actor kind" in the whole backend: only a person may create or
administer an agent, because that boundary *is* this feature — an agent cannot
spawn agents, the same way there is no agent equivalent of `services/auth.py`'s
email/password login. It uses `isinstance`, the type system's own dispatch,
rather than comparing `actor.kind` by hand. Nowhere else in this module, and
nowhere in `services/boards.py`, `services/columns.py` or `services/cards.py`,
does an agent get treated differently from a person — an agent authenticated via
`resolve_actor_by_api_key` is authorized on boards/columns/cards exactly like a
person authenticated via a session cookie.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.core.exceptions import AuthenticationError, AuthorizationError, NotFoundError
from kanbai.core.security import generate_api_key, split_api_key, verify_api_key_secret
from kanbai.models.actor import Actor, Person
from kanbai.models.agent import Agent, AgentApiKey
from kanbai.repositories import actors as actors_repository
from kanbai.repositories import agents as agents_repository

_AGENT_NOT_FOUND_MESSAGE = "El agente solicitado no existe."
_KEY_NOT_FOUND_MESSAGE = "La API key solicitada no existe."
_ONLY_PERSON_MESSAGE = "Solo una persona puede gestionar agentes."


def _require_person(actor: Actor) -> Person:
    if not isinstance(actor, Person):
        raise AuthorizationError(_ONLY_PERSON_MESSAGE)
    return actor


async def create_agent(
    session: AsyncSession, *, actor: Actor, display_name: str, description: str | None
) -> Agent:
    owner = _require_person(actor)
    agent = await agents_repository.create_agent(
        session, display_name=display_name, description=description, owner_person_id=owner.id
    )
    await session.commit()
    return agent


async def list_agents(
    session: AsyncSession, *, actor: Actor, limit: int, offset: int
) -> tuple[list[Agent], int]:
    owner = _require_person(actor)
    return await agents_repository.list_agents_for_owner(
        session, owner.id, limit=limit, offset=offset
    )


async def _get_owned_agent_or_404(
    session: AsyncSession, *, owner_id: uuid.UUID, agent_id: uuid.UUID
) -> Agent:
    agent = await agents_repository.get_agent_for_owner(session, agent_id, owner_id)
    if agent is None:
        raise NotFoundError(_AGENT_NOT_FOUND_MESSAGE)
    return agent


async def get_agent(session: AsyncSession, *, actor: Actor, agent_id: uuid.UUID) -> Agent:
    owner = _require_person(actor)
    return await _get_owned_agent_or_404(session, owner_id=owner.id, agent_id=agent_id)


async def create_api_key(
    session: AsyncSession, *, actor: Actor, agent_id: uuid.UUID
) -> tuple[AgentApiKey, str]:
    """Returns the stored row plus the plaintext key — generated here, returned
    once to the caller, and never persisted."""
    owner = _require_person(actor)
    agent = await _get_owned_agent_or_404(session, owner_id=owner.id, agent_id=agent_id)
    full_key, prefix, secret_hash = generate_api_key()
    key = await agents_repository.create_api_key(
        session, agent_id=agent.id, prefix=prefix, secret_hash=secret_hash
    )
    await session.commit()
    return key, full_key


async def list_api_keys(
    session: AsyncSession, *, actor: Actor, agent_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[AgentApiKey], int]:
    owner = _require_person(actor)
    agent = await _get_owned_agent_or_404(session, owner_id=owner.id, agent_id=agent_id)
    return await agents_repository.list_api_keys_for_agent(
        session, agent.id, limit=limit, offset=offset
    )


async def revoke_api_key(
    session: AsyncSession, *, actor: Actor, agent_id: uuid.UUID, key_id: uuid.UUID
) -> AgentApiKey:
    owner = _require_person(actor)
    agent = await _get_owned_agent_or_404(session, owner_id=owner.id, agent_id=agent_id)
    key = await agents_repository.get_api_key_for_agent(session, key_id, agent.id)
    if key is None:
        raise NotFoundError(_KEY_NOT_FOUND_MESSAGE)
    key = await agents_repository.revoke_api_key(session, key)
    await session.commit()
    return key


async def resolve_actor_by_api_key(session: AsyncSession, presented_key: str) -> Actor:
    """Called from `CurrentActor` (api/deps.py) for the `Authorization: Bearer`
    branch — never from a router directly. Every failure path (malformed key,
    unknown prefix, revoked key, wrong secret) raises the same generic
    `AuthenticationError`, so a caller can never tell which one it was."""
    parsed = split_api_key(presented_key)
    if parsed is None:
        raise AuthenticationError()
    prefix, secret = parsed

    key = await agents_repository.get_active_key_by_prefix(session, prefix)
    if key is None or not verify_api_key_secret(secret, key.secret_hash):
        raise AuthenticationError()

    actor = await actors_repository.get_actor_by_id(session, key.agent_id)
    if actor is None:
        # The FK is ON DELETE CASCADE, so this should not happen in practice.
        raise AuthenticationError()
    return actor
