"""Reusable dependencies, declared with Annotated so signatures stay readable."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.core.config import Settings
from kanbai.db.session import get_session


def get_app_settings(request: Request) -> Settings:
    """The settings this app was built with — not `get_settings()`, which always
    reads the process environment and would ignore the argument to create_app()."""
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]

# CurrentUser arrives with the authentication task and will live here as
# Annotated[User, Depends(get_current_user)]. Every endpoint that touches a
# user-owned resource must take it and filter by owner in the query.
