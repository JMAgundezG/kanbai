"""Root router for /api/v1. Every resource hangs from here."""

from fastapi import APIRouter

from kanbai.api.routers import auth, boards, cards, columns, health


def build_api_router(prefix: str) -> APIRouter:
    api_router = APIRouter(prefix=prefix)
    api_router.include_router(health.router)
    api_router.include_router(auth.router)
    api_router.include_router(boards.router)
    api_router.include_router(columns.router)
    api_router.include_router(cards.router)
    return api_router
