"""Board membership: the authorization primitive of the whole product.

The foreign key points at `actors.id`, the base of the actor hierarchy — never at
`people.actor_id`. That is the whole of CLAUDE.md's §0 invariant made concrete: this
table cannot tell a person from an agent, and no query anywhere is allowed to make
it try. TASK-09 adding an `agents` table changes nothing here.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kanbai.db.base import Base
from kanbai.models.actor import Actor


class BoardMember(Base):
    __tablename__ = "board_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    board_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # String, not a native Postgres enum, same reasoning as Actor.kind — but unlike
    # `kind` (which TASK-09 will add a third value to), no task on the board plans
    # a third role, so a CHECK constraint pins the two valid values at the database
    # level instead of leaving it to application code alone.
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # BoardMemberRead nests ActorRead; selectin avoids N+1 on every listing without
    # relying on call sites to remember .options(selectinload(...)).
    actor: Mapped[Actor] = relationship(Actor, lazy="selectin")

    __table_args__ = (
        # Named explicitly: db/base.py's `uq` convention only keys off column_0,
        # which would collide with any future single-column unique constraint on
        # board_id.
        UniqueConstraint("board_id", "actor_id", name="uq_board_members_board_id_actor_id"),
        # db/base.py's `ck` naming convention already prepends `ck_<table_name>_`,
        # so the name given here is just the suffix — passing the full
        # `ck_board_members_role` would double the prefix.
        CheckConstraint("role IN ('owner', 'member')", name="role"),
    )
