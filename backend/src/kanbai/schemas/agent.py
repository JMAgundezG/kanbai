"""Schemas for agents and their API keys."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Literal["agent"]
    display_name: str
    description: str | None
    owner_person_id: uuid.UUID
    created_at: datetime


class ApiKeyRead(BaseModel):
    """Never carries the secret: `prefix` is the only part of the key that is
    ever readable again after creation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prefix: str
    created_at: datetime
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyRead):
    """Returned only by the creation endpoint: `api_key` is the one and only
    time the plaintext value is available anywhere."""

    api_key: str
