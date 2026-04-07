"""Keycloak OIDC token validation and RBAC middleware.

Обеспечивает проверку JWT токенов, выданных Keycloak,
и извлечение ролей пользователя для авторизации.
В debug-режиме — автоматический dev-пользователь без аутентификации.
"""

import uuid
from dataclasses import dataclass, field

import httpx
import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthorizationError, HVACBaseError

logger = structlog.get_logger()

_bearer_scheme = HTTPBearer(auto_error=False)

_jwks_cache: dict | None = None

DEV_USER_ID = "00000000-0000-0000-0000-000000000001"

# HS256 tokens issued by dev bypass login (`/auth/login` when Keycloak rejects credentials).
DEV_BYPASS_JWT_ISS = "crm-dev-bypass"


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


_DEV_USER = CurrentUser(
    sub=DEV_USER_ID,
    email="dev@hvac-crm.local",
    full_name="Dev Admin",
    roles=["admin", "manager", "engineer", "warehouse_manager", "accountant"],
    raw_token="",
)


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


async def _ensure_dev_user_exists(settings: Settings) -> None:
    """Create the dev user row in the DB if it doesn't exist yet.

    Создаёт запись dev-пользователя в таблице users для корректной работы
    FK-ссылок (created_by, assigned_to и т.д.) в debug-режиме.
    """
    from app.core.database import async_session_factory
    from app.models.user import User

    async with async_session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(User).where(User.id == uuid.UUID(DEV_USER_ID))
        )
        if result.scalar_one_or_none() is None:
            session.add(User(
                id=uuid.UUID(DEV_USER_ID),
                # In debug mode token-less auth returns `sub=DEV_USER_ID`.
                # Keep `keycloak_id` aligned so user resolution works consistently.
                keycloak_id=str(DEV_USER_ID),
                email="dev@hvac-crm.local",
                full_name="Dev Admin",
                role="admin",
                is_active=True,
            ))
            await session.commit()
            logger.info("Dev user created", user_id=DEV_USER_ID)


_dev_user_ensured = False


async def authenticate_bearer_token(token: str, settings: Settings) -> CurrentUser:
    """Validate a raw Bearer JWT (dev bypass HS256 or Keycloak RS256).

    Args:
        token: JWT string without the ``Bearer`` prefix.
        settings: Application settings.

    Returns:
        CurrentUser: Parsed actor.

    Raises:
        HVACBaseError: If the token is invalid or the auth provider is unavailable.
    """
    # Dev-only HS256 JWT (same signing key as app secret); validated before Keycloak JWKS.
    try:
        dev_payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        if dev_payload.get("iss") == DEV_BYPASS_JWT_ISS:
            realm_roles = dev_payload.get("realm_access", {}).get("roles", [])
            return CurrentUser(
                sub=str(dev_payload.get("sub", "")),
                email=str(dev_payload.get("email", "")),
                full_name=str(dev_payload.get("name", "")),
                roles=realm_roles,
                raw_token=token,
            )
    except JWTError:
        pass

    try:
        jwks = await _fetch_jwks(settings)
        unverified_header = jwt.get_unverified_header(token)
        key = next(
            (k for k in jwks.get("keys", []) if k["kid"] == unverified_header.get("kid")),
            None,
        )
        if key is None:
            raise HVACBaseError(message="Invalid token signing key", code="INVALID_TOKEN", status_code=401)

        # Keycloak access tokens typically use ``aud: "account"``, not the OAuth client id.
        # The requesting client is in ``azp``; validating ``aud`` against ``keycloak_client_id`` breaks login.
        issuer = settings.keycloak_expected_issuer()
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=issuer,
                options={"verify_aud": False},
            )
        except JWTError as exc:
            try:
                unverified = jwt.get_unverified_claims(token)
                token_iss = unverified.get("iss")
                logger.warning(
                    "JWT validation failed (check issuer vs signature)",
                    expected_issuer=issuer,
                    token_iss=token_iss,
                    hint="Set KEYCLOAK_TOKEN_ISSUER to token iss if Keycloak hostname differs from KEYCLOAK_URL",
                )
            except JWTError:
                pass
            raise exc
        azp = payload.get("azp")
        if azp is not None and azp != settings.keycloak_client_id:
            raise HVACBaseError(
                message="Token was not issued for this API client",
                code="INVALID_TOKEN",
                status_code=401,
            )
    except HVACBaseError:
        raise
    except JWTError as exc:
        raise HVACBaseError(
            message=f"Token validation failed: {exc}",
            code="INVALID_TOKEN",
            status_code=401,
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Keycloak JWKS fetch failed", error=str(exc))
        raise HVACBaseError(
            message="Authentication service temporarily unavailable",
            code="AUTH_PROVIDER_UNAVAILABLE",
            status_code=503,
        ) from exc

    realm_roles: list[str] = payload.get("realm_access", {}).get("roles", [])
    return CurrentUser(
        sub=payload.get("sub", ""),
        email=payload.get("email", ""),
        full_name=payload.get("name", ""),
        roles=realm_roles,
        raw_token=token,
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Extract and validate the current user from the Authorization header.

    В debug-режиме без токена возвращает dev-пользователя с правами admin.

    Аргументы:
        request: FastAPI Request объект.
        credentials: Bearer token из заголовка Authorization.
        settings: Настройки приложения.

    Возвращает:
        CurrentUser с данными из JWT.

    Raises:
        HVACBaseError: Если токен отсутствует или невалиден (в production).
    """
    if credentials is None:
        if settings.debug:
            global _dev_user_ensured
            if not _dev_user_ensured:
                try:
                    await _ensure_dev_user_exists(settings)
                    _dev_user_ensured = True
                except Exception as exc:
                    logger.warning("Failed to ensure dev user in DB", error=str(exc))
            return _DEV_USER
        raise HVACBaseError(
            message="Authentication required",
            code="AUTH_REQUIRED",
            status_code=401,
        )

    return await authenticate_bearer_token(credentials.credentials, settings)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser | None:
    """Return the current user if Bearer credentials are valid; otherwise None.

    Used for endpoints that must not emit 401 when the client is logged out
    (e.g. best-effort cleanup after session expiry).

    Returns:
        CurrentUser if a valid token was sent, else None (missing or invalid token).
    """
    if credentials is None:
        return None
    try:
        return await authenticate_bearer_token(credentials.credentials, settings)
    except HVACBaseError:
        return None


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


def require_any_role(*roles: str):
    """Create a dependency that enforces at least one of the given roles.

    Аргументы:
        roles: Допустимые роли (достаточно одной).

    Возвращает:
        FastAPI Depends-совместимую функцию проверки ролей.
    """

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(r in user.roles for r in roles):
            raise AuthorizationError(
                required_role=", ".join(roles),
                action=f"requires one of roles: {', '.join(roles)}",
            )
        return user

    return _check
