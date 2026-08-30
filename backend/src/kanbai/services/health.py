"""Readiness rules."""

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.repositories import health as health_repository

logger = logging.getLogger(__name__)


async def is_database_reachable(session: AsyncSession) -> bool:
    """Swallow the database error on purpose: the caller turns this into a 503 and
    the details belong in the log, never in the response."""
    try:
        await health_repository.ping(session)
    except SQLAlchemyError:
        logger.exception("Database readiness probe failed")
        return False
    return True
