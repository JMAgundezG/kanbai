"""Schemas for cards."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CardCreate(BaseModel):
    column_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class CardUpdate(BaseModel):
    # Full replace over PUT, same reasoning as ColumnUpdate (TASK-05): every field
    # is required, so a client that only meant to retitle cannot silently drop the
    # description by omitting it. Moving is deliberately not here — that is
    # POST .../move, which needs a lock this endpoint has no reason to take.
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class CardMove(BaseModel):
    column_id: uuid.UUID
    # Desired 0-based index inside the destination column. The server clamps it to
    # that column's real size at execution time: the client's view can legitimately
    # be stale, and a 422 for something with an obvious right answer would only
    # force a reload. A negative index is a malformed request, not a stale view, so
    # `ge=0` rejects it with 422.
    position: int = Field(ge=0)


class CardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    column_id: uuid.UUID
    title: str
    description: str | None
    position: float
    # The plain id, not an embedded ActorRead: a page of cards would otherwise load
    # one actor per row, and no consumer of this task needs more than the id.
    created_by_actor_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
