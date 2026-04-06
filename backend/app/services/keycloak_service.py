"""Keycloak Admin REST API client.

Обёртка над Keycloak Admin API для синхронизации пользователей:
создание, назначение ролей, деактивация.
Опционально отключается через KEYCLOAK_SKIP_USER_SYNC (тесты / без Keycloak).
"""

from urllib.parse import quote

import structlog
import httpx

from app.core.config import Settings, get_settings

logger = structlog.get_logger()


class KeycloakAdminService:
    """Client for Keycloak Admin REST API.

    Атрибуты:
        settings: Конфигурация приложения.
        _token_cache: Кэш admin-токена.

    Args:
        settings: Экземпляр Settings для подключения к Keycloak.

    Returns:
        Экземпляр KeycloakAdminService.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._token_cache: str | None = None

    @property
    def _base_url(self) -> str:
        return f"{self._settings.keycloak_url}/admin/realms/{self._settings.keycloak_realm}"

    async def _admin_api_can_list_users(self, token: str) -> bool:
        """True if this token may call ``GET .../users`` on the app realm."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/users?max=1",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
        return resp.status_code == 200

    async def _fetch_client_credentials_token(self) -> str:
        """Service-account token for ``hvac-backend`` (may lack Admin API rights)."""
        token_url = (
            f"{self._settings.keycloak_url}/realms/{self._settings.keycloak_realm}"
            f"/protocol/openid-connect/token"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._settings.keycloak_client_id,
                    "client_secret": self._settings.keycloak_client_secret,
                },
                timeout=10.0,
            )
        if resp.status_code != 200:
            logger.warning(
                "Keycloak client_credentials token failed",
                status=resp.status_code,
                body=(resp.text or "")[:200],
            )
            return ""
        return str(resp.json().get("access_token", "") or "")

    async def _fetch_master_admin_token(self) -> str:
        """Master-realm admin token via public ``admin-cli`` (password grant)."""
        user = (self._settings.keycloak_admin_username or "").strip()
        password = (self._settings.keycloak_admin_password or "").strip()
        if not user or not password:
            return ""
        token_url = f"{self._settings.keycloak_url}/realms/master/protocol/openid-connect/token"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": user,
                    "password": password,
                },
                timeout=10.0,
            )
        if resp.status_code != 200:
            logger.warning(
                "Keycloak master admin token failed (check KEYCLOAK_ADMIN / KEYCLOAK_ADMIN_PASSWORD)",
                status=resp.status_code,
                body=(resp.text or "")[:200],
            )
            return ""
        return str(resp.json().get("access_token", "") or "")

    async def _get_admin_token(self) -> str:
        """Bearer token for Admin REST API on ``keycloak_realm``.

        Prefers ``hvac-backend`` client_credentials; if that token cannot list users (403),
        falls back to master-realm ``KEYCLOAK_ADMIN`` + ``admin-cli`` so deploy sync works
        without manually assigning service-account roles.
        """
        if self._token_cache:
            return self._token_cache

        tok_cc = await self._fetch_client_credentials_token()
        if tok_cc and await self._admin_api_can_list_users(tok_cc):
            self._token_cache = tok_cc
            return tok_cc

        tok_master = await self._fetch_master_admin_token()
        if tok_master and await self._admin_api_can_list_users(tok_master):
            self._token_cache = tok_master
            logger.info(
                "Keycloak Admin API token from master admin (KEYCLOAK_ADMIN); "
                "consider assigning realm-management roles to hvac-backend service account"
            )
            return tok_master

        if tok_cc:
            logger.warning(
                "Keycloak service account token cannot list users (403) and master admin fallback failed; "
                "set KEYCLOAK_ADMIN + KEYCLOAK_ADMIN_PASSWORD or fix hvac-backend service-account roles"
            )
        return ""

    async def create_user(self, email: str, full_name: str, password: str, role: str) -> str | None:
        """Create a user in Keycloak and assign realm role.

        Аргументы:
            email: Email пользователя.
            full_name: Полное имя.
            password: Начальный пароль.
            role: Роль для назначения.

        Возвращает:
            Keycloak user ID (sub) или None при ошибке.
        """
        if self._settings.keycloak_skip_user_sync:
            import uuid

            fake_id = str(uuid.uuid4())
            logger.info("Keycloak sync skipped: fake user id", email=email, fake_kc_id=fake_id)
            return fake_id

        email = (email or "").strip().lower()
        if not email:
            return None

        token = await self._get_admin_token()
        if not token:
            return None

        names = (full_name or "").strip().split(" ", 1)
        first_name = names[0] or email.split("@", 1)[0]
        # Keycloak 24+ user profile may block direct grant when lastName is empty/null.
        last_name = names[1] if len(names) > 1 else first_name

        payload = {
            "username": email,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/users",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            if resp.status_code == 201:
                location = resp.headers.get("Location", "")
                kc_id = location.rsplit("/", 1)[-1] if location else None
                if kc_id:
                    await self._sync_user_login_ready(client, token, kc_id)
                    if role:
                        await self._assign_role(client, token, kc_id, role)
                logger.info("Keycloak user created", email=email, kc_id=kc_id)
                return kc_id

            if resp.status_code == 409:
                existing = await self.get_user_id_by_email(email)
                if existing:
                    await self._sync_user_login_ready(client, token, existing)
                if existing and role:
                    await self._assign_role(client, token, existing, role)
                if existing:
                    logger.info("Keycloak user already exists, linked by email", email=email, kc_id=existing)
                return existing

            logger.warning("Keycloak user creation failed", status=resp.status_code, body=resp.text)
            return None

    async def _sync_user_login_ready(
        self,
        client: httpx.AsyncClient,
        token: str,
        user_id: str,
    ) -> None:
        """Clear required actions so password grant does not fail with 'Account is not fully set up'."""
        get_r = await client.get(
            f"{self._base_url}/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        if get_r.status_code != 200:
            return
        body = get_r.json()
        body["requiredActions"] = []
        body["emailVerified"] = True
        body["enabled"] = True
        un = (body.get("username") or body.get("email") or "user").split("@", 1)[0]
        if not (body.get("firstName") or "").strip():
            body["firstName"] = un
        if not (body.get("lastName") or "").strip():
            body["lastName"] = (body.get("firstName") or un).strip() or "-"
        put_r = await client.put(
            f"{self._base_url}/users/{user_id}",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        if put_r.status_code != 204:
            logger.warning(
                "Keycloak user login-ready sync failed",
                user_id=user_id,
                status=put_r.status_code,
            )

    async def _assign_role(self, client: httpx.AsyncClient, token: str, user_id: str, role_name: str) -> None:
        """Assign a realm role to a Keycloak user.

        Аргументы:
            client: httpx клиент.
            token: Admin-токен.
            user_id: Keycloak user ID.
            role_name: Имя роли.
        """
        roles_resp = await client.get(
            f"{self._base_url}/roles/{role_name}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        if roles_resp.status_code != 200:
            logger.warning("Keycloak role not found", role=role_name)
            return

        role_repr = roles_resp.json()
        await client.post(
            f"{self._base_url}/users/{user_id}/role-mappings/realm",
            json=[role_repr],
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )

    async def assign_realm_role(self, keycloak_user_id: str, role_name: str) -> None:
        """Map a realm role to a user (used by deploy sync; duplicates are ignored by Keycloak)."""
        if self._settings.keycloak_skip_user_sync:
            return
        token = await self._get_admin_token()
        if not token:
            return
        async with httpx.AsyncClient() as client:
            await self._assign_role(client, token, keycloak_user_id, role_name)

    async def disable_user(self, keycloak_id: str) -> bool:
        """Disable a user in Keycloak.

        Аргументы:
            keycloak_id: Keycloak user ID.

        Возвращает:
            True если успешно.
        """
        if self._settings.keycloak_skip_user_sync:
            logger.info("Keycloak sync skipped: user disable noop", kc_id=keycloak_id)
            return True

        token = await self._get_admin_token()
        if not token:
            return False

        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self._base_url}/users/{keycloak_id}",
                json={"enabled": False},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            return resp.status_code == 204

    async def verify_admin_can_query_users(self) -> bool:
        """Return True if we can obtain a token that may list users in the app realm.

        Uses service account first, then ``KEYCLOAK_ADMIN`` + ``admin-cli`` (master realm).
        """
        if self._settings.keycloak_skip_user_sync:
            logger.info("KEYCLOAK_SKIP_USER_SYNC: skipping Keycloak admin probe")
            return True
        token = await self._get_admin_token()
        if not token:
            logger.error(
                "Keycloak Admin API unavailable: fix KEYCLOAK_CLIENT_* or set "
                "KEYCLOAK_ADMIN + KEYCLOAK_ADMIN_PASSWORD (same as Keycloak console admin)."
            )
            return False
        logger.info("Keycloak Admin API reachable")
        return True

    async def get_user_id_by_email(self, email: str) -> str | None:
        """Resolve Keycloak user id by CRM email (email or username, case-insensitive)."""
        return await self.resolve_keycloak_user_id(email)

    async def resolve_keycloak_user_id(self, email: str) -> str | None:
        """Find Keycloak user id matching CRM email.

        Tries exact ``email`` and ``username`` filters (original and lowercased), then a
        bounded ``search`` match. Covers realm imports where only username is set and
        minor case differences.
        """
        if self._settings.keycloak_skip_user_sync:
            return None
        token = await self._get_admin_token()
        if not token:
            return None
        raw = (email or "").strip()
        if not raw:
            return None
        candidates = list(dict.fromkeys([raw, raw.lower()]))

        async with httpx.AsyncClient() as client:
            for field in ("email", "username"):
                for c in candidates:
                    q = quote(c, safe="")
                    resp = await client.get(
                        f"{self._base_url}/users?{field}={q}&exact=true",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10.0,
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    if data and isinstance(data, list):
                        uid = data[0].get("id")
                        if uid:
                            return str(uid)

            sq = quote(raw, safe="")
            resp = await client.get(
                f"{self._base_url}/users?search={sq}&max=50",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not isinstance(data, list):
                return None
            want = raw.lower()
            for row in data:
                em = (row.get("email") or "").strip().lower()
                un = (row.get("username") or "").strip().lower()
                if em == want or un == want:
                    uid = row.get("id")
                    if uid:
                        return str(uid)
        return None

    async def set_user_password(
        self,
        keycloak_user_id: str,
        password: str,
        *,
        temporary: bool = False,
    ) -> bool:
        """Set password for an existing Keycloak user."""
        if self._settings.keycloak_skip_user_sync:
            return True
        token = await self._get_admin_token()
        if not token:
            return False
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self._base_url}/users/{keycloak_user_id}/reset-password",
                json={"type": "password", "value": password, "temporary": temporary},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            if resp.status_code != 204:
                return False
            await self._sync_user_login_ready(client, token, keycloak_user_id)
            return True

    async def ensure_user_with_password(
        self,
        email: str,
        full_name: str,
        password: str,
        role: str,
    ) -> str | None:
        """Create user in Keycloak or update password if email already exists.

        Returns:
            Keycloak user id, or None on failure.
        """
        if self._settings.keycloak_skip_user_sync:
            import uuid

            return str(uuid.uuid4())

        email = (email or "").strip().lower()
        if not email:
            return None

        uid = await self.get_user_id_by_email(email)
        if uid:
            ok = await self.set_user_password(uid, password, temporary=False)
            if not ok:
                logger.warning("Keycloak password reset failed", email=email, kc_id=uid)
                return None
            token = await self._get_admin_token()
            if token:
                async with httpx.AsyncClient() as client:
                    await self._assign_role(client, token, uid, role)
            return uid
        return await self.create_user(email, full_name, password, role)
