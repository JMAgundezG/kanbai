"""A card: the unit of work on a board. It lives in a column, keeps its own
position inside that column, and records which actor created it.

`position` reuses TASK-05's scheme unchanged — float with a deferrable unique
constraint per column (see docs/plans/spec-TASK-05.md for why float instead of
integer reindexing) and the same GAP — so that moving a card between two
neighbours writes that one row and nothing else.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from kanbai.db.base import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Denormalized from the card's column on purpose: listing and the membership
    # filter reach the board without an extra JOIN, and the card keeps hanging off
    # the board while its column changes. services/cards.py is what keeps the two
    # in step — it only ever resolves a destination column through
    # columns_repository.get_column_by_id(board_id, ...), which filters by board.
    board_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # CASCADE so that deleting a board (which cascades into its columns) is not
    # blocked by its cards. Deleting a column *directly* while it still holds
    # cards is refused by services/columns.py with a 409, not by the database.
    column_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("board_columns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[float] = mapped_column(Float, nullable=False)
    # RESTRICT, not CASCADE: attribution is a domain invariant (CLAUDE.md § 0), so
    # removing an actor must neither delete their work nor leave it unsigned.
    created_by_actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("actors.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # `updated_at` is computed by the database (`onupdate=func.now()`), and without
    # eager_defaults SQLAlchemy would just expire the attribute after the UPDATE and
    # reload it on the next read — lazy IO, which under async raises MissingGreenlet
    # the moment the router serializes the card. With it, the UPDATE uses RETURNING
    # and the value comes back in the same round trip. Keeping the clock in the
    # database (rather than a Python-side onupdate) means created_at and updated_at
    # are always measured the same way.
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    __table_args__ = (
        # Deferrable, like board_columns: PostgreSQL checks uniqueness at COMMIT,
        # so an operation that rewrites several rows of the same column in one
        # transaction (repositories/cards.py::renumber_column) never trips over a
        # value another row of the same batch has not released yet.
        UniqueConstraint(
            "column_id",
            "position",
            name="uq_cards_column_id_position",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
