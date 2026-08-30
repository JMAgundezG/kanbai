"""Authentication rules: login, logout, session resolution, and internal person
creation (no public registration endpoint in this task — see TASK-03 scope)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.core.exceptions import AuthenticationError, ConflictError
from kanbai.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_dummy_password,
    verify_password,
)
from kanbai.models.actor import Actor, Person
from kanbai.repositories import actors as actors_repository
from kanbai.repositories import sessions as sessions_repository

_INVALID_CREDENTIALS_MESSAGE = "El email o la contraseña no son correctos."


async def create_person(
    session: AsyncSession, *, email: str, password: str, display_name: str
) -> Person:
    """Internal seeding path: used by tests and future bootstrap tooling, never by
    a router. Public registration is explicitly out of scope for this task."""
    normalized_email = email.strip().lower()
    try:
        person = await actors_repository.create_person(
            session,
            email=normalized_email,
            password_hash=hash_password(password),
            display_name=display_name,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("Ya existe una persona con ese email.") from exc
    return person


async def login(
    session: AsyncSession, *, email: str, password: str, ttl: timedelta
) -> tuple[Person, str, datetime]:
    """Same error, same message, whether the email does not exist or the password
    is wrong — the response must never reveal which one it was."""
    normalized_email = email.strip().lower()
    person = await actors_repository.get_person_by_email(session, normalized_email)

    if person is None:
        verify_dummy_password(password)
        raise AuthenticationError(_INVALID_CREDENTIALS_MESSAGE)

    if not verify_password(password, person.password_hash):
        raise AuthenticationError(_INVALID_CREDENTIALS_MESSAGE)

    token = generate_session_token()
    expires_at = datetime.now(UTC) + ttl
    await sessions_repository.create_session(
        session,
        actor_id=person.id,
        token_hash=hash_session_token(token),
        expires_at=expires_at,
    )
    await session.commit()
    return person, token, expires_at


async def resolve_actor(session: AsyncSession, token: str) -> Actor:
    auth_session = await sessions_repository.get_valid_session_by_token_hash(
        session, hash_session_token(token)
    )
    if auth_session is None:
        raise AuthenticationError()

    actor = await actors_repository.get_actor_by_id(session, auth_session.actor_id)
    if actor is None:
        # The FK is ON DELETE CASCADE, so this should not happen in practice.
        raise AuthenticationError()
    return actor


async def logout(session: AsyncSession, token: str) -> None:
    """Idempotent on purpose: logging out an already-invalid session still
    succeeds, it simply has nothing left to delete."""
    await sessions_repository.delete_session_by_token_hash(session, hash_session_token(token))
    await session.commit()
