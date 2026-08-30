"""Schemas for board columns."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ColumnCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    wip_limit: int | None = Field(default=None, gt=0)


class ColumnUpdate(BaseModel):
    # Full replace, served over PUT (not PATCH): a client sending only `name`
    # cannot silently null out `wip_limit`, since every field is required here.
    # Avoids a sentinel type to distinguish "wip_limit not sent" from "wip_limit
    # explicitly cleared to None" that a true partial PATCH would need.
    name: str = Field(min_length=1, max_length=100)
    wip_limit: int | None = Field(default=None, gt=0)


class ColumnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    name: str
    wip_limit: int | None
    position: float
    created_at: datetime


class ColumnReorder(BaseModel):
    # The complete, ordered set of column ids for the board — not a partial move.
    # Validated in services/columns.py against the board's actual columns.
    column_ids: list[uuid.UUID]
