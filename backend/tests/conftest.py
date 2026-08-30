"""Shared fixtures.

Isolation strategy: the schema is migrated once per session, and every test runs
inside an outer transaction that is rolled back afterwards. Tests therefore share
no state and do not depend on execution order.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import PostgresDsn
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from kanbai.core.config import Settings
from kanbai.db.session import get_session
from kanbai.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://kanbai:kanbai@localhost:5432/kanbai_test"


def _upgrade_to_head(database_url: str) -> None:
    """Run migrations in a worker thread.

    Alembic's async env.py calls asyncio.run(), which cannot run inside the test's
    event loop; a separate thread gets a loop of its own.
    """
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Explicit arguments outrank the environment and .env, so the suite always
    targets the test database no matter how the developer's shell is configured."""
    url = os.environ.get("KANBAI_TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    return Settings(database_url=PostgresDsn(url), environment="test")


@pytest.fixture(scope="session")
async def engine(settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        async with engine.connect():
            pass
    except SQLAlchemyError as exc:
        await engine.dispose()
        pytest.fail(
            f"No se puede conectar a la base de datos de test ({settings.database_url}). "
            "Levántala con `docker compose up -d db` desde la raíz del repo. Si el "
            "contenedor está sano pero falta la base kanbai_test, el volumen es "
            "anterior a docker/postgres/init.sql (esos scripts solo corren al "
            "inicializarlo): recréalo con `docker compose down -v && docker compose "
            f"up -d db`. Detalle: {exc}"
        )

    await asyncio.to_thread(_upgrade_to_head, str(settings.database_url))
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        # join_transaction_mode="create_savepoint" turns a commit() made by the code
        # under test into a savepoint, so the outer rollback still undoes everything.
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()


@pytest.fixture
async def app(settings: Settings, db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    application.dependency_overrides[get_session] = lambda: db_session
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
