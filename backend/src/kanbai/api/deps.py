"""Reusable dependencies, declared with Annotated so signatures stay readable."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.core.config import Settings
from kanbai.core.exceptions import AuthenticationError
from kanbai.db.session import get_session
from kanbai.models.actor import Actor
from kanbai.services import auth as auth_service


def get_app_settings(request: Request) -> Settings:
    """The settings this app was built with — not `get_settings()`, which always
    reads the process environment and would ignore the argument to create_app()."""
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_actor(request: Request, session: SessionDep, settings: SettingsDep) -> Actor:
    """The one place that resolves *who is asking*. Today it only reads the
    person's session cookie; when TASK-09 adds agent API keys, the
    `Authorization: Bearer` branch is added *inside this function* — trying the
    cookie, then the header — without changing its signature or touching any
    router or service that already depends on it. The branch is about which
    credential arrived, never about the actor's domain type (CLAUDE.md § 0)."""
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise AuthenticationError()
    return await auth_service.resolve_actor(session, token)


CurrentActor = Annotated[Actor, Depends(get_current_actor)]
