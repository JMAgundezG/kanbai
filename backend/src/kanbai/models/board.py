"""A board: a workspace with its own members. From here on, "can I see this" means
"am I a member of its board" — TASK-05 onward scopes columns, cards, comments and
events through the same membership.

No `owner_id` column: "who owns this board" lives entirely in `board_members` (a
row with `role="owner"`), never duplicated here — two sources of truth for the same
fact would eventually disagree.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from kanbai.db.base import Base


class Board(Base):
    __tablename__ = "boards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
