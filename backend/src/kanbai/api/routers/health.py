"""Health endpoints.

Two of them, on purpose. Liveness answers "is the process up?" and must stay cheap
and dependency-free — an orchestrator restarts the container when it fails.
Readiness answers "can it serve traffic?" and therefore does reach the database.
"""

from http import HTTPStatus

from fastapi import APIRouter, Response

from kanbai.api.deps import SessionDep
from kanbai.schemas.health import HealthRead, ReadinessRead
from kanbai.services.health import is_database_reachable

# Mounted at the root, outside /api/v1: it is infrastructure, not part of the API
# contract consumed by the frontend.
liveness_router = APIRouter(tags=["health"])

router = APIRouter(prefix="/health", tags=["health"])


@liveness_router.get(
    "/health",
    response_model=HealthRead,
    status_code=HTTPStatus.OK,
    summary="Comprobación de vida del servicio",
)
async def liveness() -> HealthRead:
    return HealthRead()


@router.get(
    "/ready",
    response_model=ReadinessRead,
    status_code=HTTPStatus.OK,
    summary="Comprobación de disponibilidad, incluida la base de datos",
    responses={
        HTTPStatus.SERVICE_UNAVAILABLE: {
            "model": ReadinessRead,
            "description": "La base de datos no está disponible.",
        }
    },
)
async def readiness(session: SessionDep, response: Response) -> ReadinessRead:
    if not await is_database_reachable(session):
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return ReadinessRead(status="error", database="error")
    return ReadinessRead(status="ok", database="ok")
