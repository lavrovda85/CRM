"""Align CRM ``users.keycloak_id`` with Keycloak users (deploy / one-shot).

For each active CRM user:
- If ``KEYCLOAK_SYNC_INITIAL_PASSWORD`` is set: **always** call Keycloak ensure (create if
  missing, or **reset password** to that value for every user). Updates ``keycloak_id`` in CRM.
  Remove or empty the variable after bootstrap so deploys do not keep resetting passwords.
- If it is unset: link ``keycloak_id`` by email only; warn when no Keycloak user exists.

PostgreSQL does **not** store login passwords; they exist only in Keycloak. Passwords typed
in the CRM "create user" form are sent to Keycloak at creation time only. If users were
created with ``KEYCLOAK_SKIP_USER_SYNC=true`` or Keycloak was unreachable, those
passwords were never applied—use this sync with ``KEYCLOAK_SYNC_INITIAL_PASSWORD`` or
``POST /users/{id}/keycloak-sync`` to provision credentials.

Run: ``python -m app.cli.keycloak_sync``
"""

from __future__ import annotations

import asyncio
import os
import sys

import structlog
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models.user import User
from app.services.keycloak_service import KeycloakAdminService

logger = structlog.get_logger(__name__)

_MAX_DB_WAIT_ATTEMPTS = 30
_DB_WAIT_SECONDS = 2


async def _load_users(session: AsyncSession) -> list[User]:
    res = await session.execute(select(User).where(User.is_active.is_(True)).order_by(User.email))
    return list(res.scalars().all())


async def run_sync() -> int:
    """Execute CRM ↔ Keycloak user alignment.

    Returns:
        Process exit code (0 = success).
    """
    settings = get_settings()
    if settings.keycloak_skip_user_sync:
        logger.error("KEYCLOAK_SKIP_USER_SYNC is true; Keycloak sync is disabled")
        return 2

    initial_pw = (os.environ.get("KEYCLOAK_SYNC_INITIAL_PASSWORD") or "").strip()
    kc = KeycloakAdminService(settings)
    logger.info("Keycloak sync preflight", initial_password_configured=bool(initial_pw))
    if not await kc.verify_admin_can_query_users():
        logger.error(
            "Keycloak sync cannot call Admin API. Pass KEYCLOAK_ADMIN and KEYCLOAK_ADMIN_PASSWORD "
            "(same as Keycloak console) into the keycloak-sync service — sync will use them automatically. "
            "Alternatively assign realm-management roles to hvac-backend's service account in Keycloak UI."
        )
        return 3

    for attempt in range(_MAX_DB_WAIT_ATTEMPTS):
        try:
            async with async_session_factory() as session:
                users = await _load_users(session)
                updated = 0
                skipped = 0
                passwords_applied = 0

                for u in users:
                    if initial_pw:
                        new_id = await kc.ensure_user_with_password(
                            u.email,
                            u.full_name,
                            initial_pw,
                            u.role,
                        )
                        if not new_id:
                            logger.error(
                                "Failed to ensure Keycloak user (check Admin API roles)",
                                email=u.email,
                            )
                            return 1
                        if (u.keycloak_id or "").strip() != new_id:
                            u.keycloak_id = new_id
                            updated += 1
                            logger.info(
                                "Linked keycloak_id",
                                email=u.email,
                                keycloak_id=new_id,
                            )
                        passwords_applied += 1
                        continue

                    kc_id = await kc.get_user_id_by_email(u.email)
                    if kc_id:
                        if (u.keycloak_id or "").strip() != kc_id:
                            u.keycloak_id = kc_id
                            updated += 1
                            logger.info(
                                "Updated keycloak_id from Keycloak",
                                email=u.email,
                                keycloak_id=kc_id,
                            )
                        await kc.assign_realm_role(kc_id, u.role)
                    else:
                        logger.warning(
                            "No Keycloak user for CRM email; set KEYCLOAK_SYNC_INITIAL_PASSWORD "
                            "to create accounts (CRM does not store passwords—only Keycloak does)",
                            email=u.email,
                        )
                        skipped += 1

                await session.commit()
                logger.info(
                    "Keycloak CRM sync finished",
                    users_total=len(users),
                    keycloak_id_updated=updated,
                    skipped_missing_keycloak=skipped,
                    keycloak_passwords_applied_to_all=passwords_applied,
                )
                return 0

        except (OperationalError, ProgrammingError) as exc:
            if attempt < _MAX_DB_WAIT_ATTEMPTS - 1:
                logger.warning(
                    "Database not ready for Keycloak sync, retrying",
                    attempt=attempt + 1,
                    error=str(exc),
                )
                await asyncio.sleep(_DB_WAIT_SECONDS)
                continue
            logger.exception("Keycloak sync failed after DB wait")
            return 1
        except Exception:
            logger.exception("Keycloak sync failed")
            return 1

    return 1


def main() -> None:
    code = asyncio.run(run_sync())
    sys.exit(code)


if __name__ == "__main__":
    main()
