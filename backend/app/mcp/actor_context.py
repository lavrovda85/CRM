"""Runtime actor context for MCP tools when invoked outside standalone MCP.

When the AI assistant (HTTP) runs MCP-equivalent tools, it sets the current
Keycloak-backed user via a context variable so tools use the same actor as
the REST API. Standalone MCP keeps the previous dev/service behaviour.

Атрибуты контекста:
    ``ContextVar`` хранит ``CurrentUser`` для текущего async-запроса;
    если не задан — используется прежняя логика dev/production для MCP.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.core.security import CurrentUser, DEV_USER_ID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_tool_actor: ContextVar[CurrentUser | None] = ContextVar("mcp_tool_actor", default=None)
# When set (e.g. by HTTP AI assistant), maps JWT subject to CRM ``users.id`` for FK columns.
_resolved_users_id: ContextVar[uuid.UUID | None] = ContextVar("mcp_resolved_users_id", default=None)


def set_tool_actor(user: CurrentUser | None) -> Token:
    """Bind ``user`` as the actor for nested MCP tool calls.

    Возвращает:
        Токен для ``reset_tool_actor``.
    """
    return _tool_actor.set(user)


def reset_tool_actor(token: Token) -> None:
    """Restore the previous actor binding."""
    _tool_actor.reset(token)


def set_resolved_users_id(uid: uuid.UUID) -> Token:
    """Bind internal ``users.id`` for ``actor_dict_for_service`` (JWT sub may differ)."""
    return _resolved_users_id.set(uid)


def reset_resolved_users_id(token: Token) -> None:
    """Clear resolved user id binding."""
    _resolved_users_id.reset(token)


def _default_mcp_user() -> CurrentUser:
    """Fallback actor when no HTTP user is bound (standalone MCP)."""
    settings = get_settings()
    if settings.debug:
        return CurrentUser(
            sub=DEV_USER_ID,
            email="dev@hvac-crm.local",
            preferred_username="dev",
            full_name="Dev Admin",
            roles=["admin", "manager", "engineer", "warehouse_manager", "accountant"],
            raw_token="",
        )
    return CurrentUser(
        sub=DEV_USER_ID,
        email="",
        preferred_username="",
        roles=["admin"],
        raw_token="",
    )


def current_mcp_user() -> CurrentUser:
    """Return the actor for MCP tool execution (HTTP user or MCP default)."""
    bound = _tool_actor.get()
    if bound is not None:
        return bound
    return _default_mcp_user()


def current_mcp_user_sub() -> str:
    """Return the subject (user id string) for the current MCP actor."""
    return current_mcp_user().sub


def actor_dict_for_service() -> dict[str, Any]:
    """Dict shape expected by ``TaskService`` / template helpers: ``{\"id\": UUID}``."""
    resolved = _resolved_users_id.get()
    if resolved is not None:
        return {"id": resolved}
    sub = current_mcp_user_sub()
    try:
        return {"id": uuid.UUID(sub)}
    except ValueError as exc:
        raise ValueError(
            "Cannot map MCP actor sub to users.id; use HTTP assistant or DEV UUID sub."
        ) from exc


async def resolve_mcp_actor_users_table_id(db: AsyncSession) -> uuid.UUID:
    """Resolve CRM ``users.id`` for MCP tools (JWT ``sub`` may differ from PK).

    When the HTTP assistant binds an actor, prefer ``set_resolved_users_id`` — then this
    returns that id. Otherwise resolves via ``keycloak_id`` / ``users.id`` like REST API.

    Raises:
        NotFoundError: No matching CRM user row.
    """
    rid = _resolved_users_id.get()
    if rid is not None:
        return rid
    from app.services.user_identity import resolve_users_table_id

    return await resolve_users_table_id(db, current_mcp_user())
