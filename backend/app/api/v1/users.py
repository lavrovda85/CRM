"""User management API endpoints.

CRUD операции над пользователями с синхронизацией Keycloak.
Создание и деактивация — только для admin.
"""

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from botocore.exceptions import ClientError
import boto3
from botocore.config import Config as BotoConfig

from app.core.config import Settings, get_settings
from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import DuplicateError, HVACBaseError, NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser, require_role
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserKeycloakSyncRequest,
    UserListItem,
    UserResponse,
    UserSelfUpdate,
    UserUpdate,
)
from app.services.keycloak_service import KeycloakAdminService
from app.services.user_identity import resolve_users_table_id

router = APIRouter(prefix="/users")


async def _resolve_current_db_user(db: AsyncSession, token_user: CurrentUser) -> User:
    """Load the DB row for the JWT subject (internal id or Keycloak id)."""
    uid = await resolve_users_table_id(db, token_user)
    db_user = await db.get(User, uid)
    if not db_user:
        raise NotFoundError("User", token_user.sub)
    return db_user


def _avatar_storage_key(user_id: uuid.UUID) -> str:
    """Build deterministic object key for user avatar."""
    return f"avatars/{user_id}/avatar"


def _get_s3_client(settings: Settings):
    """Build MinIO S3 client."""
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> UserResponse:
    """Get the current authenticated user's profile.

    Возвращает профиль текущего аутентифицированного пользователя.

    Аргументы:
        db: Сессия БД.
        user: Текущий пользователь.

    Возвращает:
        Профиль пользователя.
    """
    db_user = await _resolve_current_db_user(db, user)
    return UserResponse.model_validate(db_user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user_profile(
    body: UserSelfUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> UserResponse:
    """Update own profile (phone, display name). Does not require admin role."""
    db_user = await _resolve_current_db_user(db, user)
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return UserResponse.model_validate(db_user)
    await db.execute(update(User).where(User.id == db_user.id).values(**update_data))
    await db.flush()
    await db.refresh(db_user)
    return UserResponse.model_validate(db_user)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_role("admin")),
) -> UserResponse:
    """Create a new user and sync to Keycloak.

    Создаёт пользователя в БД и Keycloak. Только для администраторов.

    Аргументы:
        body: Данные нового пользователя.
        db: Сессия БД.
        user: Текущий пользователь (admin).

    Возвращает:
        Созданного пользователя.
    """
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise DuplicateError("User", "email", body.email)

    settings = get_settings()
    kc_service = KeycloakAdminService()
    kc_id = await kc_service.create_user(body.email, body.full_name, body.password, body.role)
    if not settings.keycloak_skip_user_sync and not kc_id:
        raise HVACBaseError(
            message=(
                "Keycloak user creation failed. Check KEYCLOAK_URL, realm, client credentials, "
                "and that the backend client service account has manage-users."
            ),
            code="KEYCLOAK_USER_CREATE_FAILED",
            status_code=502,
        )

    db_user = User(
        keycloak_id=kc_id or f"local-{uuid.uuid4()}",
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        role=body.role,
        position=body.position,
        is_active=True,
    )
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)
    return UserResponse.model_validate(db_user)


@router.post("/{user_id}/keycloak-sync", response_model=UserResponse)
async def sync_user_to_keycloak(
    user_id: uuid.UUID,
    body: UserKeycloakSyncRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_role("admin")),
) -> UserResponse:
    """Create or update the user in Keycloak and refresh ``keycloak_id`` in CRM.

    Use this to repair accounts created while Keycloak sync was skipped, or after
    changing the email in CRM.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", str(user_id))

    settings = get_settings()
    if settings.keycloak_skip_user_sync:
        raise ValidationError(
            "keycloak",
            "KEYCLOAK_SKIP_USER_SYNC is enabled; disable it to sync users to Keycloak",
        )

    kc = KeycloakAdminService()
    new_id = await kc.ensure_user_with_password(
        db_user.email,
        db_user.full_name,
        body.password,
        db_user.role,
    )
    if not new_id:
        raise HVACBaseError(
            message="Keycloak sync failed (see server logs)",
            code="KEYCLOAK_SYNC_FAILED",
            status_code=502,
        )

    db_user.keycloak_id = new_id
    await db.flush()
    await db.refresh(db_user)
    return UserResponse.model_validate(db_user)


@router.get("", response_model=PaginatedResponse[UserListItem])
async def list_users(
    role: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[UserListItem]:
    """List users with optional filters.

    Возвращает постраничный список пользователей.

    Аргументы:
        role: Фильтр по роли.
        is_active: Фильтр по активности.
        search: Поиск по имени/email.
        pagination: Параметры пагинации.
        db: Сессия БД.
        user: Текущий пользователь.

    Возвращает:
        Постраничный список пользователей.
    """
    query = select(User)
    count_query = select(func.count(User.id))

    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        search_filter = or_(User.full_name.ilike(pattern), User.email.ilike(pattern))
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(User.full_name).offset(pagination.offset).limit(pagination.limit)
    )
    users = result.scalars().all()

    return PaginatedResponse(
        items=[UserListItem.model_validate(u) for u in users],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> UserResponse:
    """Get user details.

    Аргументы:
        user_id: UUID пользователя.
        db: Сессия БД.
        user: Текущий пользователь.

    Возвращает:
        Детальную информацию о пользователе.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", str(user_id))
    return UserResponse.model_validate(db_user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_role("admin")),
) -> UserResponse:
    """Update user fields (admin only).

    Аргументы:
        user_id: UUID пользователя.
        body: Поля для обновления.
        db: Сессия БД.
        user: Текущий пользователь (admin).

    Возвращает:
        Обновлённого пользователя.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", str(user_id))

    update_data = body.model_dump(exclude_unset=True)
    new_password = update_data.pop("password", None)

    if new_password is not None:
        settings = get_settings()
        if settings.keycloak_skip_user_sync:
            raise ValidationError(
                "keycloak",
                "KEYCLOAK_SKIP_USER_SYNC is enabled; cannot change Keycloak password",
            )
        kc = KeycloakAdminService()
        new_kc_id = await kc.ensure_user_with_password(
            db_user.email,
            db_user.full_name,
            new_password,
            db_user.role,
        )
        if not new_kc_id:
            raise HVACBaseError(
                message="Keycloak password update failed (see server logs)",
                code="KEYCLOAK_PASSWORD_FAILED",
                status_code=502,
            )
        if (db_user.keycloak_id or "").strip() != new_kc_id:
            update_data["keycloak_id"] = new_kc_id

    if update_data:
        await db.execute(update(User).where(User.id == user_id).values(**update_data))
        await db.flush()
        await db.refresh(db_user)

    return UserResponse.model_validate(db_user)


@router.delete("/{user_id}", status_code=204)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_role("admin")),
) -> None:
    """Deactivate a user (soft delete) and disable in Keycloak.

    Аргументы:
        user_id: UUID пользователя.
        db: Сессия БД.
        user: Текущий пользователь (admin).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", str(user_id))

    await db.execute(update(User).where(User.id == user_id).values(is_active=False))
    await db.flush()

    kc_service = KeycloakAdminService()
    await kc_service.disable_user(db_user.keycloak_id)


@router.post("/{user_id}/avatar", response_model=UserResponse)
async def upload_user_avatar(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> UserResponse:
    """Upload user avatar to MinIO and update `avatar_url`."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise ValidationError("file", "Only image uploads are allowed for avatar")

    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", str(user_id))

    # Non-admin can upload avatar only for themselves.
    is_self = current_user.sub == str(user_id) or current_user.sub == db_user.keycloak_id
    if current_user.role != "admin" and not is_self:
        raise ValidationError("user_id", "Not enough permissions to upload this avatar")

    body = await file.read()
    if len(body) > 5 * 1024 * 1024:
        raise ValidationError("file", "Avatar must be <= 5MB")

    key = _avatar_storage_key(user_id)
    s3 = _get_s3_client(settings)
    try:
        s3.put_object(
            Bucket=settings.minio_bucket,
            Key=key,
            Body=body,
            ContentType=file.content_type,
            CacheControl="public, max-age=300",
        )
    except ClientError as exc:
        raise ValidationError("file", f"Avatar upload failed: {exc}") from exc

    db_user.avatar_url = f"/api/v1/users/{user_id}/avatar"
    await db.flush()
    await db.refresh(db_user)
    return UserResponse.model_validate(db_user)


@router.get("/{user_id}/avatar")
async def get_user_avatar(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Return avatar image bytes by user id (public endpoint)."""
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", str(user_id))

    s3 = _get_s3_client(settings)
    key = _avatar_storage_key(user_id)
    try:
        obj = s3.get_object(Bucket=settings.minio_bucket, Key=key)
        content = obj["Body"].read()
        media_type = obj.get("ContentType", "image/jpeg")
    except ClientError as exc:
        raise NotFoundError("Avatar", str(user_id)) from exc
    return Response(content=content, media_type=media_type)
