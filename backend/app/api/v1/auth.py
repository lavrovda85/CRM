"""Authentication endpoints.

Provides:
- `/auth/login` to exchange user credentials for Keycloak tokens;
- `/auth/refresh` to rotate access tokens using a refresh token;
- `/auth/me` to return the current authenticated user's profile.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from app.core.config import get_settings
from app.core.dependencies import get_db
import structlog

from app.core.exceptions import HVACBaseError
from app.core.security import DEV_BYPASS_JWT_ISS, CurrentUser, get_current_user
from app.models.user import User
from app.schemas.auth import AuthLoginRequest, AuthRefreshRequest, AuthTokens, AuthUser
from app.services.company_service import ensure_default_company_for_user, get_membership


router = APIRouter(prefix="/auth")
logger = structlog.get_logger(__name__)
_REFRESH_COOKIE = "hvac_refresh_token"

_ROLE_PRIORITY = ("admin", "manager", "warehouse_manager", "accountant", "engineer")


def _crm_role_from_realm_roles(roles: list[str]) -> str:
    """Pick primary CRM role from Keycloak realm roles (first match by priority)."""
    s = set(roles or [])
    for r in _ROLE_PRIORITY:
        if r in s:
            return r
    return "engineer"


async def _resolve_or_provision_db_user(
    db: AsyncSession,
    current_user: CurrentUser,
    *,
    fallback_email: str | None = None,
) -> User:
    """Load ``users`` row or create it from Keycloak JWT claims (first successful login).

    Keycloak realm users exist independently of PostgreSQL; CRM requires a local row for FKs.
    """
    uid = (current_user.sub or "").strip()
    if not uid:
        raise HVACBaseError(
            message="Invalid token subject",
            code="INVALID_TOKEN",
            status_code=401,
        )

    # Keycloak ``sub`` is a UUID string; CRM ``users.id`` is often a different UUID. Always match on
    # ``keycloak_id`` when ``sub`` is UUID-shaped, not only on ``users.id``.
    uuid_uid: UUID | None
    try:
        uuid_uid = UUID(uid)
    except ValueError:
        uuid_uid = None

    db_user = None
    if uuid_uid is not None:
        r1 = await db.execute(select(User).where(User.id == uuid_uid))
        db_user = r1.scalar_one_or_none()
    if db_user is None:
        r2 = await db.execute(select(User).where(User.keycloak_id == uid))
        db_user = r2.scalar_one_or_none()
    if db_user is not None:
        return db_user

    email_raw = (current_user.email or fallback_email or "").strip()
    if not email_raw:
        raise HVACBaseError(
            message="Cannot create CRM user: missing email (configure email in Keycloak)",
            code="USER_PROVISION_MISSING_EMAIL",
            status_code=400,
        )
    email_norm = email_raw.lower()

    dup = await db.execute(select(User).where(User.email == email_norm))
    if dup.scalar_one_or_none() is not None:
        raise HVACBaseError(
            message="This email is already linked to another CRM account",
            code="EMAIL_CONFLICT",
            status_code=409,
        )

    full_name = (current_user.full_name or "").strip() or email_norm.split("@")[0]
    role = _crm_role_from_realm_roles(current_user.roles)

    kwargs: dict = {
        "keycloak_id": uid,
        "email": email_norm,
        "full_name": full_name,
        "role": role,
        "is_active": True,
    }
    if uuid_uid is not None:
        kwargs["id"] = uuid_uid

    db_user = User(**kwargs)
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)
    logger.info("Provisioned CRM user from Keycloak", email=email_norm, keycloak_sub=uid)
    return db_user


async def _keycloak_password_grant(
    *,
    email: str,
    password: str,
    settings,
) -> AuthTokens:
    """Perform Keycloak password grant.

    Args:
        email: Keycloak username.
        password: User password.
        settings: Application settings.

    Returns:
        AuthTokens parsed from Keycloak response.
    """
    token_url = (
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        f"/protocol/openid-connect/token"
    )

    # Keycloak username is case-sensitive; CRM emails are matched case-insensitively in DB.
    username = (email or "").strip().lower()
    if not username:
        raise HVACBaseError(
            message="Invalid credentials",
            code="AUTH_FAILED",
            status_code=401,
            details={},
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type": "password",
                "client_id": settings.keycloak_client_id,
                "client_secret": settings.keycloak_client_secret,
                "username": username,
                "password": password,
                "scope": "openid profile email",
            },
            timeout=15.0,
        )

    if resp.status_code != 200:
        kc_err = ""
        try:
            kc_err = str((resp.json() or {}).get("error") or "")
        except Exception:
            pass
        logger.warning(
            "Keycloak password grant rejected",
            status=resp.status_code,
            keycloak_error=kc_err,
            username=username,
        )
        # Do not leak Keycloak internals to the client.
        raise HVACBaseError(
            message="Invalid credentials",
            code="AUTH_FAILED",
            status_code=401,
            details={"provider_status": resp.status_code},
        )

    data = resp.json()
    # Keycloak standard response fields:
    # access_token, refresh_token, token_type, expires_in
    return AuthTokens(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", ""),
        token_type=data.get("token_type", "Bearer"),
        expires_in=int(data.get("expires_in", 0)),
    )


def _issue_dev_bypass_tokens(db_user: User, settings) -> AuthTokens:
    """Issue HS256 JWTs signed with app secret for local/dev login without Keycloak.

    Args:
        db_user: CRM user row (password already verified against DEV_BYPASS_PASSWORD).
        settings: Application settings (secret_key, expiry).

    Returns:
        AuthTokens with access and refresh set to the same signed JWT (refresh rotates via /auth/refresh).
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=48)
    exp_ts = int(exp.timestamp())
    role = db_user.role or "engineer"
    payload = {
        "sub": str(db_user.id),
        "email": db_user.email,
        "name": db_user.full_name,
        "iss": DEV_BYPASS_JWT_ISS,
        "realm_access": {"roles": [role]},
        "exp": exp_ts,
        "iat": int(now.timestamp()),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return AuthTokens(
        access_token=token,
        refresh_token=token,
        token_type="Bearer",
        expires_in=48 * 3600,
    )


async def _dev_bypass_login_from_db(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    settings,
) -> tuple[AuthTokens, User] | None:
    """If dev bypass is enabled and password matches env, return tokens for DB user."""
    expected = (settings.dev_bypass_password or "").strip()
    if not expected:
        return None
    if not (settings.debug or settings.dev_bypass_auth):
        return None
    try:
        pw_ok = secrets.compare_digest(
            password.encode("utf-8"),
            expected.encode("utf-8"),
        )
    except ValueError:
        return None
    if not pw_ok:
        return None

    email_norm = email.strip().lower()
    result = await db.execute(select(User).where(User.email == email_norm))
    db_user = result.scalar_one_or_none()
    if db_user is None or not db_user.is_active:
        return None
    return _issue_dev_bypass_tokens(db_user, settings), db_user


async def _keycloak_refresh_grant(*, refresh_token: str, settings) -> AuthTokens:
    """Perform Keycloak refresh_token grant.

    Args:
        refresh_token: Previously issued OAuth2 refresh token.
        settings: Application settings.

    Returns:
        New AuthTokens from Keycloak.

    Raises:
        HVACBaseError: If Keycloak rejects the refresh request.
    """
    token_url = (
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        f"/protocol/openid-connect/token"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.keycloak_client_id,
                "client_secret": settings.keycloak_client_secret,
                "refresh_token": refresh_token,
            },
            timeout=15.0,
        )

    if resp.status_code != 200:
        raise HVACBaseError(
            message="Refresh token invalid or expired",
            code="AUTH_REFRESH_FAILED",
            status_code=401,
            details={"provider_status": resp.status_code},
        )

    data = resp.json()
    return AuthTokens(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token") or refresh_token,
        token_type=data.get("token_type", "Bearer"),
        expires_in=int(data.get("expires_in", 0)),
    )


def _user_to_auth_user(u: User) -> AuthUser:
    """Map DB user to frontend AuthUser shape."""
    return AuthUser(
        id=str(u.id),
        email=u.email,
        full_name=u.full_name,
        role=u.role,
        is_active=u.is_active,
        avatar_url=u.avatar_url,
        phone=u.phone,
        created_at=u.created_at,
        updated_at=u.updated_at,
    )


def _set_refresh_cookie(response: Response, refresh_token: str, request: Request) -> None:
    """Persist refresh token in cookie for longer browser session."""
    settings = get_settings()
    secure = request.url.scheme == "https"
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh_token,
        max_age=settings.auth_cookie_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def _clear_refresh_cookie(response: Response, request: Request) -> None:
    """Clear refresh cookie on logout."""
    secure = request.url.scheme == "https"
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path="/",
        samesite="lax",
        secure=secure,
    )


@router.post("/login", response_model=dict)
async def login(
    body: AuthLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Login user and return Keycloak tokens + user profile.

    Args:
        body: Login request.
        request: FastAPI Request (used for token decoding utilities).
        db: Async DB session.

    Returns:
        Dictionary containing:
          - `tokens`: Keycloak tokens
          - `user`: authenticated user profile
    """
    settings = get_settings()
    db_user: User | None = None
    tokens: AuthTokens

    try:
        tokens = await _keycloak_password_grant(
            email=body.email,
            password=body.password,
            settings=settings,
        )
    except HVACBaseError as exc:
        if exc.code != "AUTH_FAILED":
            raise
        bypass = await _dev_bypass_login_from_db(
            db,
            email=body.email,
            password=body.password,
            settings=settings,
        )
        if bypass is None:
            raise
        tokens, db_user = bypass

    if db_user is None:
        cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=tokens.access_token)
        current_user: CurrentUser = await get_current_user(
            request=request,
            credentials=cred,
            settings=settings,
        )

        try:
            db_user = await _resolve_or_provision_db_user(
                db, current_user, fallback_email=body.email
            )
        except HVACBaseError:
            raise
        except Exception as exc:
            raise HVACBaseError(
                message="Failed to resolve user",
                code="USER_RESOLVE_FAILED",
                status_code=500,
                details={"error": str(exc)},
            ) from exc

    if not db_user.is_active:
        raise HVACBaseError(
            message="User is disabled",
            code="USER_DISABLED",
            status_code=403,
        )

    default_company_id = await ensure_default_company_for_user(db, db_user.id)
    active_company_id = default_company_id
    if body.company_id is not None:
        m = await get_membership(db, user_id=db_user.id, company_id=body.company_id)
        if m is None:
            raise HVACBaseError(
                message="You are not a member of the selected company",
                code="COMPANY_ACCESS_DENIED",
                status_code=403,
                details={"company_id": str(body.company_id)},
            )
        active_company_id = body.company_id
    _set_refresh_cookie(response, tokens.refresh_token, request)

    return {
        "tokens": tokens.model_dump(),
        "user": _user_to_auth_user(db_user).model_dump(),
        "active_company_id": str(active_company_id),
    }


@router.post("/refresh", response_model=dict)
async def refresh_session(
    body: AuthRefreshRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Rotate access token using a refresh token (Keycloak).

    Args:
        body: Refresh request with refresh_token.
        request: FastAPI Request (used for token decoding utilities).
        db: Async DB session.

    Returns:
        Dictionary containing new `tokens` and resolved `user` profile.
    """
    settings = get_settings()
    db_user: User | None = None
    tokens: AuthTokens

    try:
        refresh_token = (body.refresh_token or "").strip() or request.cookies.get(_REFRESH_COOKIE, "").strip()
        if not refresh_token:
            raise HVACBaseError(
                message="Refresh token is required",
                code="AUTH_REFRESH_FAILED",
                status_code=401,
            )
        tokens = await _keycloak_refresh_grant(
            refresh_token=refresh_token,
            settings=settings,
        )
    except HVACBaseError as exc:
        if exc.code != "AUTH_REFRESH_FAILED":
            raise
        try:
            payload = jwt.decode(
                refresh_token,
                settings.secret_key,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except JWTError:
            raise exc
        if payload.get("iss") != DEV_BYPASS_JWT_ISS:
            raise exc
        try:
            uid = UUID(str(payload.get("sub")))
        except (ValueError, TypeError):
            raise exc
        row = await db.get(User, uid)
        if row is None or not row.is_active:
            raise exc
        tokens = _issue_dev_bypass_tokens(row, settings)
        db_user = row

    if db_user is None:
        cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials=tokens.access_token)
        current_user: CurrentUser = await get_current_user(
            request=request,
            credentials=cred,
            settings=settings,
        )

        try:
            db_user = await _resolve_or_provision_db_user(db, current_user, fallback_email=None)
        except HVACBaseError:
            raise
        except Exception as exc:
            raise HVACBaseError(
                message="Failed to resolve user",
                code="USER_RESOLVE_FAILED",
                status_code=500,
                details={"error": str(exc)},
            ) from exc

    if not db_user.is_active:
        raise HVACBaseError(
            message="User is disabled",
            code="USER_DISABLED",
            status_code=403,
        )

    _set_refresh_cookie(response, tokens.refresh_token, request)
    return {
        "tokens": tokens.model_dump(),
        "user": _user_to_auth_user(db_user).model_dump(),
    }


@router.post("/logout", response_model=dict)
async def logout(
    request: Request,
    response: Response,
) -> dict:
    """Clear auth cookies (best-effort endpoint for browser logout)."""
    _clear_refresh_cookie(response, request)
    return {"ok": True}


@router.get("/me", response_model=AuthUser)
async def me(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AuthUser:
    """Get the current authenticated user's profile.

    Args:
        db: Async DB session.
        user: CurrentUser extracted from the JWT token.

    Returns:
        AuthUser profile.
    """
    try:
        db_user = await _resolve_or_provision_db_user(db, user, fallback_email=None)
    except HVACBaseError:
        raise
    except Exception as exc:
        raise HVACBaseError(
            message="Failed to resolve user profile",
            code="USER_RESOLVE_FAILED",
            status_code=500,
            details={"error": str(exc)},
        ) from exc

    if not db_user.is_active:
        raise HVACBaseError(
            message="User is disabled",
            code="USER_DISABLED",
            status_code=403,
        )

    return _user_to_auth_user(db_user)

