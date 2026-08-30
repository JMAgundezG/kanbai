"""Queries on login sessions."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.models.session import AuthSession


async def create_session(
    session: AsyncSession, *, actor_id: uuid.UUID, token_hash: str, expires_at: datetime
) -> AuthSession:
    auth_session = AuthSession(actor_id=actor_id, token_hash=token_hash, expires_at=expires_at)
    session.add(auth_session)
    await session.flush()
    return auth_session


async def get_valid_session_by_token_hash(
    session: AsyncSession, token_hash: str
) -> AuthSession | None:
    result = await session.execute(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash,
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    return result.scalar_one_or_none()


async def delete_session_by_token_hash(session: AsyncSession, token_hash: str) -> None:
    await session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))
