"""Schemas for actors — the participant that signs every action on the board."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ActorRead(BaseModel):
    """Deliberately without `email`: an actor is identified by type and visible
    name, not by its credential. Keeps this schema agnostic of the actor's kind —
    when TASK-09 adds agents, the same schema serves them without changes."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Literal["person", "agent"]
    display_name: str
    created_at: datetime
