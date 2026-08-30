"""Health checks that need to reach the database."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def ping(session: AsyncSession) -> None:
    """Round-trip to PostgreSQL. Raises SQLAlchemyError if it cannot be reached."""
    await session.execute(text("SELECT 1"))
