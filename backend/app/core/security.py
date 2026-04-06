"""Keycloak OIDC token validation and RBAC middleware.

Обеспечивает проверку JWT токенов, выданных Keycloak,
и извлечение ролей пользователя для авторизации.
"""

from dataclasses import dataclass, field

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthorizationError, HVACBaseError

_bearer_scheme = HTTPBearer(auto_error=False)

_jwks_cache: dict | None = None


@dataclass(frozen=True)
class CurrentUser:
    """Represents the authenticated user extracted from the JWT token.

    Атрибуты:
        sub: Keycloak subject (user ID).
        email: Email пользователя.
        full_name: Полное имя.
        roles: Список ролей из realm_access.
        raw_token: Исходный JWT токен.
    """

    sub: str
    email: str = ""
    full_name: str = ""
    roles: list[str] = field(default_factory=list)
    raw_token: str = ""


async def _fetch_jwks(settings: Settings) -> dict:
    """Fetch and cache JWKS from Keycloak.

    Аргументы:
        settings: Настройки приложения.

    Возвращает:
        JWKS (JSON Web Key Set) от Keycloak.
    """
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    jwks_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url, timeout=10.0)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Extract and validate the current user from the Authorization header.

    Аргументы:
        request: FastAPI Request объект.
        credentials: Bearer token из заголовка Authorization.
        settings: Настройки приложения.

    Возвращает:
        CurrentUser с данными из JWT.

    Raises:
        HVACBaseError: Если токен отсутствует или невалиден.
    """
    if credentials is None:
        raise HVACBaseError(
            message="Authentication required",
            code="AUTH_REQUIRED",
            status_code=401,
        )

    token = credentials.credentials
    try:
        jwks = await _fetch_jwks(settings)
        unverified_header = jwt.get_unverified_header(token)
        key = next(
            (k for k in jwks.get("keys", []) if k["kid"] == unverified_header.get("kid")),
            None,
        )
        if key is None:
            raise HVACBaseError(message="Invalid token signing key", code="INVALID_TOKEN", status_code=401)

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
            issuer=f"{settings.keycloak_url}/realms/{settings.keycloak_realm}",
        )
    except JWTError as exc:
        raise HVACBaseError(
            message=f"Token validation failed: {exc}",
            code="INVALID_TOKEN",
            status_code=401,
        ) from exc

    realm_roles: list[str] = payload.get("realm_access", {}).get("roles", [])
    return CurrentUser(
        sub=payload.get("sub", ""),
        email=payload.get("email", ""),
        full_name=payload.get("name", ""),
        roles=realm_roles,
        raw_token=token,
    )


def require_role(role: str):
    """Create a dependency that enforces a specific role.

    Аргументы:
        role: Требуемая роль (например, "admin", "manager", "engineer").

    Возвращает:
        FastAPI Depends-совместимую функцию проверки роли.
    """

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if role not in user.roles:
            raise AuthorizationError(required_role=role, action=f"requires role '{role}'")
        return user

    return _check
