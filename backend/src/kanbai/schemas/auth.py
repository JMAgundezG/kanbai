"""Schemas for person authentication."""

from pydantic import BaseModel, EmailStr, SecretStr


class LoginRequest(BaseModel):
    email: EmailStr
    # SecretStr keeps the password out of reprs, so it never leaks into a log line
    # or an error trace that happens to print this model.
    password: SecretStr
