"""Queries on actors and people. The only place that talks SQL for this domain."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.models.actor import Actor, Person


async def get_person_by_email(session: AsyncSession, email: str) -> Person | None:
    result = await session.execute(select(Person).where(Person.email == email))
    return result.scalar_one_or_none()


async def create_person(
    session: AsyncSession, *, email: str, password_hash: str, display_name: str
) -> Person:
    person = Person(email=email, password_hash=password_hash, display_name=display_name)
    session.add(person)
    await session.flush()
    return person


async def get_actor_by_id(session: AsyncSession, actor_id: uuid.UUID) -> Actor | None:
    """Loading the base class already yields the concrete subclass instance
    (`Person` today, `Agent` once TASK-09 exists) — no branching needed here."""
    result = await session.execute(select(Actor).where(Actor.id == actor_id))
    return result.scalar_one_or_none()
