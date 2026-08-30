"""Queries on agents and their API keys. The only place that talks SQL here."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.models.agent import Agent, AgentApiKey


async def create_agent(
    session: AsyncSession, *, display_name: str, description: str | None, owner_person_id: uuid.UUID
) -> Agent:
    agent = Agent(
        display_name=display_name, description=description, owner_person_id=owner_person_id
    )
    session.add(agent)
    await session.flush()
    return agent


async def list_agents_for_owner(
    session: AsyncSession, owner_person_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[Agent], int]:
    total = await session.scalar(
        select(func.count()).select_from(Agent).where(Agent.owner_person_id == owner_person_id)
    )
    result = await session.execute(
        select(Agent)
        .where(Agent.owner_person_id == owner_person_id)
        .order_by(Agent.created_at, Agent.actor_id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def get_agent_for_owner(
    session: AsyncSession, agent_id: uuid.UUID, owner_person_id: uuid.UUID
) -> Agent | None:
    result = await session.execute(
        select(Agent).where(Agent.actor_id == agent_id, Agent.owner_person_id == owner_person_id)
    )
    return result.scalar_one_or_none()


async def create_api_key(
    session: AsyncSession, *, agent_id: uuid.UUID, prefix: str, secret_hash: str
) -> AgentApiKey:
    key = AgentApiKey(agent_id=agent_id, prefix=prefix, secret_hash=secret_hash)
    session.add(key)
    await session.flush()
    return key


async def list_api_keys_for_agent(
    session: AsyncSession, agent_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[AgentApiKey], int]:
    total = await session.scalar(
        select(func.count()).select_from(AgentApiKey).where(AgentApiKey.agent_id == agent_id)
    )
    result = await session.execute(
        select(AgentApiKey)
        .where(AgentApiKey.agent_id == agent_id)
        .order_by(AgentApiKey.created_at, AgentApiKey.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def get_api_key_for_agent(
    session: AsyncSession, key_id: uuid.UUID, agent_id: uuid.UUID
) -> AgentApiKey | None:
    result = await session.execute(
        select(AgentApiKey).where(AgentApiKey.id == key_id, AgentApiKey.agent_id == agent_id)
    )
    return result.scalar_one_or_none()


async def get_active_key_by_prefix(session: AsyncSession, prefix: str) -> AgentApiKey | None:
    """The one query the authentication path runs: an indexed, exact-match lookup
    on `prefix`, filtering out revoked keys in the same query — never a scan that
    hashes and compares every stored key."""
    result = await session.execute(
        select(AgentApiKey).where(AgentApiKey.prefix == prefix, AgentApiKey.revoked_at.is_(None))
    )
    return result.scalar_one_or_none()


async def revoke_api_key(session: AsyncSession, key: AgentApiKey) -> AgentApiKey:
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        await session.flush()
    return key
