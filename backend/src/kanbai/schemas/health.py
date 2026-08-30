"""Schemas for the health endpoints."""

from typing import Literal

from pydantic import BaseModel


class HealthRead(BaseModel):
    """Liveness: the process is up. Says nothing about its dependencies."""

    status: Literal["ok"] = "ok"


class ReadinessRead(BaseModel):
    """Readiness: the process can actually serve traffic."""

    status: Literal["ok", "error"]
    database: Literal["ok", "error"]
