"""Application factory and wiring."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from kanbai import __version__
from kanbai.api.router import build_api_router
from kanbai.api.routers import health
from kanbai.core.config import Settings, get_settings
from kanbai.core.exceptions import KanbaiError
from kanbai.core.logging import configure_logging
from kanbai.db.session import build_engine, build_sessionmaker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    engine: AsyncEngine = app.state.engine
    await engine.dispose()


async def handle_kanbai_error(request: Request, exc: Exception) -> JSONResponse:
    """One handler for the whole domain hierarchy: each error carries its status."""
    error = exc if isinstance(exc, KanbaiError) else KanbaiError()
    if error.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        # A domain error that maps to 5xx is a bug on our side: it must leave a
        # trace in the log even though the client only sees a generic message.
        logger.exception("Domain error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=error.status_code, content={"detail": error.message})


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor."},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Taking settings as an argument is what lets the test suite build the app
    against the test database without touching the process environment. Everything
    derived from them — engine, session factory — hangs off `app.state`, so no
    request can reach a different configuration by accident."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # The interactive docs describe every endpoint and payload: useful everywhere
    # except on a public production deployment.
    is_production = settings.environment == "production"

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="API de tableros kanban de kanbai.",
        lifespan=lifespan,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    engine = build_engine(settings)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = build_sessionmaker(engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.cors_origins],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.add_exception_handler(KanbaiError, handle_kanbai_error)
    app.add_exception_handler(Exception, handle_unexpected_error)

    app.include_router(health.liveness_router)
    app.include_router(build_api_router(settings.api_v1_prefix))

    return app
