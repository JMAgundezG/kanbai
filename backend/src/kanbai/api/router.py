"""Root router for /api/v1. Every resource hangs from here."""

from fastapi import APIRouter

from kanbai.api.routers import health


def build_api_router(prefix: str) -> APIRouter:
    api_router = APIRouter(prefix=prefix)
    api_router.include_router(health.router)
    return api_router
