"""The actor hierarchy: whoever signs an action on the board, person or agent.

Joined-table inheritance on purpose: `actors` carries only what every actor has in
common (id, discriminator, visible name, creation time); `people` carries only what
a person needs (email, password hash). TASK-09 adds an `agents` table the same way,
without migrating or touching either of these tables. No query outside the
authentication layer branches on `kind` — loading an actor by id already returns the
concrete subclass.

`with_polymorphic="*"` on the base mapper: a query against `Actor` (e.g.
`repositories.actors.get_actor_by_id`) outer-joins every subclass table
(`people`, `agents`) and populates their columns in the same round trip, instead
of the SQLAlchemy default of loading only the base columns and lazily fetching a
subclass's own columns the first time Python code touches one. That default is
fine as long as nothing reads a subclass-only attribute on a polymorphically
loaded `Actor` — true until TASK-09: `permission_ceiling_actor_id` (below) is the
first thing in this codebase to read a subclass column (`Agent.owner_person_id`)
off an object that came from a base-class query, and in a genuinely fresh
session (every real request gets one — see db/session.py) that lazy fetch runs
outside of any `await`, which SQLAlchemy's async support cannot do: it raises
`MissingGreenlet` instead of quietly blocking. `with_polymorphic` closes that
trap for every future subclass column too, not just this one.
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
        "with_polymorphic": "*",
    }

    def permission_ceiling_actor_id(self) -> uuid.UUID | None:
        """The actor whose access this actor's access must never exceed, or
        `None` if none applies. A person has no ceiling: their access derives
        only from their own memberships. `Agent` (models/agent.py) is the only
        subclass that overrides this, returning its owning person's id.

        This is the polymorphic hook `services/boards.py` calls instead of
        reading `kind` to keep "an agent never outranks the person who created
        it" (CLAUDE.md § 0) true without a single `if actor.kind == "agent"`
        anywhere in the domain.
        """
        return None


class Person(Actor):
    """A human actor: signs in with email and password."""

    __tablename__ = "people"

    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    __mapper_args__ = {"polymorphic_identity": "person"}  # noqa: RUF012
