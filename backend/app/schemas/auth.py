"""Authentication schemas.

Промежуточные Pydantic-схемы для авторизации пользователей:
- запрос логина (`/auth/login`);
- выдача токенов (Keycloak);
- получение профиля текущего пользователя (`/auth/me`).
"""

import uuid

from datetime import datetime

from pydantic import BaseModel, Field


class AuthLoginRequest(BaseModel):
    """Login request schema.

    Attributes:
        email: User email (Keycloak username).
        password: User password.
        company_id: Optional active tenant after login (must be a membership of the user).
    """

    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)
    company_id: uuid.UUID | None = None


class AuthRefreshRequest(BaseModel):
    """Refresh-token request schema for Keycloak token rotation.

    Attributes:
        refresh_token: OAuth2 refresh token previously issued by Keycloak.
    """

    refresh_token: str = Field(..., min_length=10, max_length=16000)


class AuthTokens(BaseModel):
    """Keycloak OAuth tokens.

    Attributes:
        access_token: JWT access token.
        refresh_token: Refresh token.
        token_type: Token type (e.g. Bearer).
        expires_in: Access token lifetime in seconds.
    """

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class AuthUser(BaseModel):
    """Authenticated user profile returned to the frontend.

    Attributes:
        id: User identifier in the local database (UUID).
        email: Email address.
        full_name: Full name.
        role: Primary role in CRM.
        is_active: Whether user is active.
        avatar_url: Optional avatar URL.
        phone: Optional phone.
        created_at: Account creation timestamp.
        updated_at: Account update timestamp.
    """

    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    avatar_url: str | None = None
    phone: str | None = None
    created_at: datetime
    updated_at: datetime

