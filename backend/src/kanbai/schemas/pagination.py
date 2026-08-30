"""Generic paginated response shape, reused by every listing endpoint."""

from pydantic import BaseModel


class Page[ItemT](BaseModel):
    items: list[ItemT]
    total: int
    page: int
    size: int
