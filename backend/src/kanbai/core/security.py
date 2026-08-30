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


# --- agent API keys ---------------------------------------------------------
#
# Same "only a hash touches the database" pattern as the session token above,
# plus a plaintext, indexed `prefix` so a presented key is found with a direct
# lookup (repositories.agents.get_active_key_by_prefix) instead of a table scan
# that hashes and compares every stored key — the "no SELECT de todas las keys"
# requirement from TASK-09. The secret itself is already high-entropy random
# data, unlike a human-chosen password, so a fast SHA-256 (not Argon2) plus a
# constant-time comparison is the right tool, not a weaker one.

_API_KEY_HEADER_PREFIX = "kanbai_agent_"
_API_KEY_PREFIX_BYTES = 9  # ~12 base64url chars
_API_KEY_SECRET_BYTES = 32  # ~43 base64url chars


def generate_api_key() -> tuple[str, str, str]:
    """Returns `(full_key, prefix, secret_hash)`. `full_key` is
    `kanbai_agent_<prefix>.<secret>` — handed to the caller once, in the creation
    response, and never stored. Only `prefix` (plaintext) and `secret_hash` are."""
    prefix = secrets.token_urlsafe(_API_KEY_PREFIX_BYTES)
    secret = secrets.token_urlsafe(_API_KEY_SECRET_BYTES)
    full_key = f"{_API_KEY_HEADER_PREFIX}{prefix}.{secret}"
    return full_key, prefix, hash_api_key_secret(secret)


def hash_api_key_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def split_api_key(key: str) -> tuple[str, str] | None:
    """`(prefix, secret)` from a presented key, or `None` if it is malformed."""
    if not key.startswith(_API_KEY_HEADER_PREFIX):
        return None
    prefix, separator, secret = key.removeprefix(_API_KEY_HEADER_PREFIX).partition(".")
    if not separator or not prefix or not secret:
        return None
    return prefix, secret


def verify_api_key_secret(secret: str, secret_hash: str) -> bool:
    return secrets.compare_digest(hash_api_key_secret(secret), secret_hash)
