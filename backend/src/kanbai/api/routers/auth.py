"""Person authentication: login, logout, and who-am-I.

Agents (TASK-09) authenticate with an `Authorization: Bearer` API key instead — a
different scheme handled entirely inside `CurrentActor`, so nothing here changes
when that lands.
"""

from datetime import timedelta
from http import HTTPStatus

from fastapi import APIRouter, Request, Response

from kanbai.api.deps import CurrentActor, SessionDep, SettingsDep
from kanbai.schemas.actor import ActorRead
from kanbai.schemas.auth import LoginRequest
from kanbai.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, settings: SettingsDep, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        httponly=True,
        # Only production is guaranteed to sit behind TLS: "local" is plain HTTP
        # dev, and "test" runs the ASGI transport in-process over HTTP too — a
        # Secure cookie in either would be silently dropped by any real client.
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


@router.post(
    "/login",
    response_model=ActorRead,
    status_code=HTTPStatus.OK,
    summary="Inicia sesión con email y contraseña",
    responses={
        HTTPStatus.UNAUTHORIZED: {"description": "Las credenciales no son válidas."},
    },
)
async def login(
    credentials: LoginRequest, session: SessionDep, settings: SettingsDep, response: Response
) -> ActorRead:
    person, token, _ = await auth_service.login(
        session,
        email=credentials.email,
        password=credentials.password.get_secret_value(),
        ttl=timedelta(days=settings.session_ttl_days),
    )
    _set_session_cookie(response, settings, token)
    return ActorRead.model_validate(person)


@router.post(
    "/logout",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Cierra la sesión actual",
)
async def logout(
    request: Request, session: SessionDep, settings: SettingsDep, response: Response
) -> None:
    """Idempotent: with no cookie, or an already-expired one, this still returns
    204 — closing a session that is not open is not an error."""
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await auth_service.logout(session, token)
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get(
    "/me",
    response_model=ActorRead,
    status_code=HTTPStatus.OK,
    summary="Actor autenticado en la sesión actual",
    responses={
        HTTPStatus.UNAUTHORIZED: {"description": "No hay una sesión activa."},
    },
)
async def me(actor: CurrentActor) -> ActorRead:
    return ActorRead.model_validate(actor)
