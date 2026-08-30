"""Domain errors.

Each subclass carries the HTTP status it maps to, so `main.py` needs a single
handler for the whole hierarchy. Messages are user-facing and therefore Spanish,
and never leak internals (SQL, paths, tracebacks).
"""

from http import HTTPStatus


class KanbaiError(Exception):
    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    default_message: str = "Error interno del servidor."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(KanbaiError):
    """Also used when a resource exists but belongs to someone else: we answer 404
    rather than 403 so the response does not confirm that it exists."""

    status_code = HTTPStatus.NOT_FOUND
    default_message = "El recurso solicitado no existe."


class ConflictError(KanbaiError):
    status_code = HTTPStatus.CONFLICT
    default_message = "El recurso entra en conflicto con otro que ya existe."


class ValidationError(KanbaiError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    default_message = "Los datos enviados no son válidos."


class AuthorizationError(KanbaiError):
    """The actor already knows the resource exists — they are a member of its
    board — but lacks the role an action requires (e.g. renaming a board without
    being its owner). Distinct from NotFoundError, which is for an actor with no
    visibility into the resource at all and must never confirm it exists."""

    status_code = HTTPStatus.FORBIDDEN
    default_message = "No tienes permisos suficientes para esta acción."


class AuthenticationError(KanbaiError):
    """Credentials missing, invalid, or a session that no longer resolves.

    The default message covers "no session at all"; login failure passes its own
    message, deliberately identical whether the email does not exist or the
    password is wrong — the response must never reveal which.
    """

    status_code = HTTPStatus.UNAUTHORIZED
    default_message = "No has iniciado sesión."
