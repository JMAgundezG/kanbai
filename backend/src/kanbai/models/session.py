"""A person's login session.

Not part of the actor hierarchy: a session is an authentication artifact, not a
domain participant. Named `AuthSession`, not `Session`, so it never collides with
`sqlalchemy.ext.asyncio.AsyncSession` (or `Session`) in modules that import both.

The token itself never touches the database: only its SHA-256 hash does, the same
pattern TASK-09 will reuse for agent API keys. Losing the `sessions` table (or a
leaked backup of it) never leaks anything an attacker can present as a cookie.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from kanbai.db.base import Base


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
