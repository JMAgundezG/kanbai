"""Schemas for boards."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BoardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class BoardUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class BoardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime
    # The requesting actor's own role on this board. Not a `Board` column — the
    # router assembles it from the (board, role) pair the service returns. Cheap
    # (already queried to authorize the request) and needed by the frontend to
    # decide what to show, e.g. only an owner sees a "delete board" action.
    role: Literal["owner", "member"]
