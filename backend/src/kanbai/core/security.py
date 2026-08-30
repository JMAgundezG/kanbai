"""Password hashing and session token generation.

Argon2id via `argon2-cffi`: OWASP's current recommendation for new code, and
unlike `passlib` (the historically common choice) it is actively maintained.

Session tokens follow the pattern TASK-09 will reuse for agent API keys: a random
token handed to the client, only its SHA-256 hash stored server-side. Losing the
table never leaks anything an attacker can present as a credential.
"""

import contextlib
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

# Computed once, checked when an email does not exist at all, so a login attempt
# against an unknown address costs about the same as one against a real account —
# otherwise the response latency itself would reveal which emails are registered.
_DUMMY_HASH = _hasher.hash("no existe pero tarda lo mismo")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Never raises: a malformed stored hash is a mismatch, not a server error."""
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError, VerificationError, InvalidHashError:
        return False


def verify_dummy_password(password: str) -> None:
    """Burns the same time as `verify_password` without touching real data."""
    with contextlib.suppress(VerifyMismatchError, VerificationError, InvalidHashError):
        _hasher.verify(_DUMMY_HASH, password)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
