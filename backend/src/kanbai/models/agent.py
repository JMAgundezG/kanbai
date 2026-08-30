"""The agent actor, and the API keys it authenticates with.

`Agent` is joined-table inheritance exactly like `Person` (see models/actor.py) —
adding this table changes nothing in `actors` or `people`. `display_name` and
`created_at` are inherited from `Actor`, unchanged.

`AgentApiKey` follows the same pattern as `models/session.py`: only a hash ever
touches the database. It additionally stores a plaintext, indexed `prefix` so a
presented key can be located with a direct lookup instead of a table scan that
compares every stored hash.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from kanbai.db.base import Base
from kanbai.models.actor import Actor


class Agent(Actor):
    """An automated actor, created and owned by a person."""

    __tablename__ = "agents"

    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # CASCADE, not RESTRICT (contrast Card.created_by_actor_id): an agent with no
    # owning person left has nothing worth preserving — there is no attribution
    # record that deleting it would orphan.
    owner_person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.actor_id", ondelete="CASCADE"), nullable=False, index=True
    )

    __mapper_args__ = {"polymorphic_identity": "agent"}  # noqa: RUF012

    def permission_ceiling_actor_id(self) -> uuid.UUID:
        return self.owner_person_id


class AgentApiKey(Base):
    __tablename__ = "agent_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.actor_id", ondelete="CASCADE"), nullable=False, index=True
    )
    prefix: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Not deleted, not a boolean: keeping the row (and when it was revoked) is
    # what lets "revoked" and "never existed" be told apart in tests without
    # exposing that distinction to a caller — both dead ends resolve to the same
    # generic 401.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
