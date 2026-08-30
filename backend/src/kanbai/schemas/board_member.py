"""Schemas for board membership."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from kanbai.schemas.actor import ActorRead


class BoardMemberCreate(BaseModel):
    actor_id: uuid.UUID
    role: Literal["owner", "member"] = "member"


class BoardMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    # Reuses ActorRead as-is: indifferent to person vs. agent by construction, no
    # new field needed for either kind.
    actor: ActorRead
    role: Literal["owner", "member"]
    created_at: datetime
