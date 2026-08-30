"""Async engine, session factory and the request-scoped session dependency."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from kanbai.core.config import Settings


def build_engine(settings: Settings) -> AsyncEngine:
    """Creating an engine opens no connection, so this is safe to call while the
    app is being built — and it keeps the engine tied to the settings that app was
    created with instead of to whatever the process environment happens to say."""
    return create_async_engine(
        str(settings.database_url),
        echo=settings.db_echo,
        pool_pre_ping=True,
    )


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False is mandatory in async: otherwise reading an attribute
    # after a commit triggers lazy IO outside of an await.
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a session for the duration of one request.

    The session factory comes from this app's state, never from a module-level
    global: a global built from `get_settings()` would silently connect the test
    suite to the developer's database the day some code stops going through this
    dependency.

    Committing is the service layer's job, not this dependency's: an endpoint that
    performs two operations must be able to decide its own unit of work.
    """
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
