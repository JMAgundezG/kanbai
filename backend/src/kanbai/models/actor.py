"""The actor hierarchy: whoever signs an action on the board, person or agent.

Joined-table inheritance on purpose: `actors` carries only what every actor has in
common (id, discriminator, visible name, creation time); `people` carries only what
a person needs (email, password hash). TASK-09 adds an `agents` table the same way,
without migrating or touching either of these tables. No query outside the
authentication layer branches on `kind` — loading an actor by id already returns the
concrete subclass.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from kanbai.db.base import Base


class Actor(Base):
    __tablename__ = "actors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # String, not a native Postgres enum: TASK-09 adding "agent" as a value would
    # otherwise require an ALTER TYPE migration, the exact fragility Alembic
    # handles worst.
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # SQLAlchemy mapper configuration, never per-instance state — but the
    # SQLAlchemy/mypy plugin rejects a ClassVar override here (it treats
    # `__mapper_args__` as declared on DeclarativeBase), so RUF012 stays silenced
    # instead of fighting the plugin.
    __mapper_args__ = {  # noqa: RUF012
        "polymorphic_identity": "actor",
        "polymorphic_on": "kind",
    }


class Person(Actor):
    """A human actor: signs in with email and password."""

    __tablename__ = "people"

    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    __mapper_args__ = {"polymorphic_identity": "person"}  # noqa: RUF012
