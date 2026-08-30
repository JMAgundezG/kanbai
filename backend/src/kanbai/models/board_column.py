"""A board column: one phase of the board's workflow. Named `BoardColumn`, not
`Column`, to avoid shadowing `sqlalchemy.Column` and to match the `boards`/
`board_members` naming precedent.

`position` is a float with a deferrable unique constraint per board — see
docs/plans/spec-TASK-05.md for why float instead of integer reindexing. TASK-06
copies this exact mechanism for `cards.position`.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from kanbai.db.base import Base


class BoardColumn(Base):
    __tablename__ = "board_columns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    board_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # None = no WIP limit. TASK-06 enforces this when moving cards; this task only
    # stores it.
    wip_limit: Mapped[int | None] = mapped_column(nullable=True)
    position: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Deferrable: PostgreSQL checks uniqueness at COMMIT, not per-statement, so
        # a full reorder can write several rows in any order inside one transaction
        # without a row momentarily colliding with another row's old value.
        UniqueConstraint(
            "board_id",
            "position",
            name="uq_board_columns_board_id_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        # db/base.py's `ck` naming convention already prepends `ck_<table_name>_`,
        # so the name given here is just the suffix.
        CheckConstraint("wip_limit IS NULL OR wip_limit > 0", name="wip_limit_positive"),
    )
