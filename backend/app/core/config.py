"""Application configuration loaded from environment variables.

Использует pydantic-settings для валидации и загрузки конфигурации
из переменных окружения или .env файла.
"""

from functools import lru_cache
import json
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _discover_env_files() -> tuple[str, ...] | str:
    """Resolve .env paths so repo-root config works when CWD is ``backend/``.

    В Docker образе рабочая директория обычно ``/app``; корневой ``.env`` репозитория
    там не смонтирован — переменные должны приходить из ``environment`` (compose).

    Возвращает:
        Кортеж существующих путей к ``.env`` или ``\".env\"`` для поведения по умолчанию.
    """
    here = Path(__file__).resolve()
    backend_dir = here.parents[2]
    repo_root = here.parents[3]
    candidates = (repo_root / ".env", backend_dir / ".env")
    found = [str(p) for p in candidates if p.is_file()]
    return tuple(found) if found else ".env"


class Settings(BaseSettings):
    """Central application settings.

    Атрибуты:
        app_name: Название приложения.
        app_version: Версия приложения.
        debug: Режим отладки.
        secret_key: Секретный ключ для подписи токенов.
        log_level: Уровень логирования.
        database_url: Async URL для подключения к PostgreSQL.
        database_url_sync: Sync URL для Alembic миграций.
        redis_url: URL для подключения к Redis.
        celery_broker_url: URL брокера Celery.
        celery_result_backend: URL бэкенда результатов Celery.
        minio_endpoint: Эндпоинт MinIO S3.
        minio_access_key: Ключ доступа MinIO.
        minio_secret_key: Секретный ключ MinIO.
        minio_bucket: Имя бакета для документов.
        keycloak_url: URL сервера Keycloak.
        keycloak_realm: Realm Keycloak.
        keycloak_client_id: Client ID бэкенда.
        keycloak_client_secret: Client Secret бэкенда.
        cors_origins: Разрешённые CORS origins.
        backend_host: Хост бэкенда.
        backend_port: Порт бэкенда.
        mcp_host: Хост MCP сервера.
        mcp_port: Порт MCP сервера.
        telegram_bot_token: Токен Telegram бота.
        openai_api_key: Ключ OpenAI для чата-ассистента (опционально).
        openai_model: Идентификатор модели OpenAI.
        ai_assistant_max_tool_rounds: Макс. число раундов tool-calling за один запрос.
    """

    model_config = SettingsConfigDict(
        env_file=_discover_env_files(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Empty env values (e.g. TASK_SCHEDULER_OBSERVER_IDS=) must not be JSON-decoded as lists.
        env_ignore_empty=True,
    )

    app_name: str = "SPEC CRM"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, alias="BACKEND_DEBUG")
    schema_bootstrap_on_startup: bool = Field(
        default=False,
        alias="SCHEMA_BOOTSTRAP_ON_STARTUP",
        description="Run create_all + dev parity DDL on startup (use true once on new prod DB).",
    )
    secret_key: str = "change-me"
    log_level: str = "INFO"

    database_url: str
    database_url_sync: str = ""
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"
    celery_sla_check_every_minutes: int = Field(default=15, ge=1, le=1440, alias="CELERY_SLA_CHECK_EVERY_MINUTES")
    celery_overdue_check_every_minutes: int = Field(default=30, ge=1, le=1440, alias="CELERY_OVERDUE_CHECK_EVERY_MINUTES")
    celery_task_notifications_scan_every_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
        alias="CELERY_TASK_NOTIFICATIONS_SCAN_EVERY_MINUTES",
    )
    celery_daily_summary_hour: int = Field(default=20, ge=0, le=23, alias="CELERY_DAILY_SUMMARY_HOUR")
    celery_daily_summary_minute: int = Field(default=0, ge=0, le=59, alias="CELERY_DAILY_SUMMARY_MINUTE")
    celery_monthly_depreciation_day_of_month: int = Field(
        default=1,
        ge=1,
        le=28,
        alias="CELERY_MONTHLY_DEPRECIATION_DAY_OF_MONTH",
    )
    celery_monthly_depreciation_hour: int = Field(default=2, ge=0, le=23, alias="CELERY_MONTHLY_DEPRECIATION_HOUR")
    celery_monthly_depreciation_minute: int = Field(
        default=0,
        ge=0,
        le=59,
        alias="CELERY_MONTHLY_DEPRECIATION_MINUTE",
    )
    task_scheduler_enabled: bool = Field(default=False, alias="TASK_SCHEDULER_ENABLED")
    task_scheduler_cron_minute: str = Field(default="0", alias="TASK_SCHEDULER_CRON_MINUTE")
    task_scheduler_cron_hour: str = Field(default="9", alias="TASK_SCHEDULER_CRON_HOUR")
    task_scheduler_cron_day_of_month: str = Field(default="*", alias="TASK_SCHEDULER_CRON_DAY_OF_MONTH")
    task_scheduler_cron_month_of_year: str = Field(default="*", alias="TASK_SCHEDULER_CRON_MONTH_OF_YEAR")
    task_scheduler_cron_day_of_week: str = Field(default="1-5", alias="TASK_SCHEDULER_CRON_DAY_OF_WEEK")
    task_scheduler_title: str = Field(default="Scheduled task", alias="TASK_SCHEDULER_TITLE")
    task_scheduler_description: str | None = Field(default=None, alias="TASK_SCHEDULER_DESCRIPTION")
    task_scheduler_priority: str = Field(default="medium", alias="TASK_SCHEDULER_PRIORITY")
    task_scheduler_template_id: str | None = Field(default=None, alias="TASK_SCHEDULER_TEMPLATE_ID")
    task_scheduler_assigned_to: str | None = Field(default=None, alias="TASK_SCHEDULER_ASSIGNED_TO")
    task_scheduler_requested_by: str | None = Field(default=None, alias="TASK_SCHEDULER_REQUESTED_BY")
    task_scheduler_board_id: str | None = Field(default=None, alias="TASK_SCHEDULER_BOARD_ID")
    task_scheduler_client_id: str | None = Field(default=None, alias="TASK_SCHEDULER_CLIENT_ID")
    task_scheduler_due_in_hours: int = Field(default=24, ge=0, le=24 * 31, alias="TASK_SCHEDULER_DUE_IN_HOURS")
    task_scheduler_observer_ids: list[str] = Field(default_factory=list, alias="TASK_SCHEDULER_OBSERVER_IDS")
    task_scheduler_co_assignee_ids: list[str] = Field(default_factory=list, alias="TASK_SCHEDULER_CO_ASSIGNEE_IDS")
    task_scheduler_dedup_window_minutes: int = Field(
        default=180,
        ge=1,
        le=24 * 60,
        alias="TASK_SCHEDULER_DEDUP_WINDOW_MINUTES",
    )

    # Internal MinIO endpoint used by backend services running in Docker.
    minio_endpoint: str = "http://minio:9000"
    # Public MinIO endpoint used to generate presigned URLs for the browser.
    # It must be reachable FROM the user's browser.
    minio_public_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_secret"
    minio_bucket: str = "hvac-documents"

    keycloak_url: str = "http://keycloak:8080"
    keycloak_realm: str = "hvac"
    keycloak_client_id: str = "hvac-backend"
    keycloak_client_secret: str = "backend-secret-change-me"
    # If Keycloak puts a different `iss` in access tokens than KEYCLOAK_URL/realms/... (hostname/proxy), set this.
    keycloak_token_issuer: str | None = Field(default=None, alias="KEYCLOAK_TOKEN_ISSUER")
    # Master-realm admin (fallback when hvac-backend service account lacks realm-management roles).
    keycloak_admin_username: str = Field(default="", alias="KEYCLOAK_ADMIN")
    keycloak_admin_password: str = Field(default="", alias="KEYCLOAK_ADMIN_PASSWORD")

    # When Keycloak password grant fails: allow login if email exists in DB and password
    # matches DEV_BYPASS_PASSWORD (requires BACKEND_DEBUG or DEV_BYPASS_AUTH=true).
    dev_bypass_auth: bool = Field(default=False, alias="DEV_BYPASS_AUTH")
    dev_bypass_password: str | None = Field(default=None, alias="DEV_BYPASS_PASSWORD")
    # If true: user CRUD skips Keycloak Admin API (fake keycloak_id). Breaks real login unless DEV_BYPASS_PASSWORD is used.
    keycloak_skip_user_sync: bool = Field(default=False, alias="KEYCLOAK_SKIP_USER_SYNC")

    cors_origins: list[str] = ["http://localhost:3000"]
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001

    telegram_bot_token: str = ""

    # OpenAI (AI assistant chat — same MCP tools as standalone MCP server)
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    # HTTP proxy only for OpenAI SDK (e.g. http://xray-openai:10808). Xray should route OpenAI -> VLESS, else direct.
    openai_http_proxy: str | None = Field(default=None, alias="OPENAI_HTTP_PROXY")
    ai_assistant_max_tool_rounds: int = Field(default=24, ge=1, le=48, alias="AI_ASSISTANT_MAX_TOOL_ROUNDS")
    ai_assistant_timezone: str = Field(
        default="Europe/Moscow",
        alias="AI_ASSISTANT_TIMEZONE",
        description="IANA timezone for interpreting «сегодня»/«завтра» in AI assistant (server clock).",
    )
    yandex_geocoder_api_key: str | None = Field(default=None, alias="YANDEX_GEOCODER_API_KEY")

    # Tender import: fetch pages and optional web search (MCP / AI tools)
    tender_fetch_timeout_seconds: float = Field(default=25.0, ge=5.0, le=120.0, alias="TENDER_FETCH_TIMEOUT_SECONDS")
    tender_fetch_max_bytes: int = Field(default=2_000_000, ge=50_000, le=10_000_000, alias="TENDER_FETCH_MAX_BYTES")
    tender_fetch_allow_insecure_http: bool = Field(
        default=False,
        alias="TENDER_FETCH_ALLOW_INSECURE_HTTP",
        description="Allow http:// URLs when fetching tender pages (default: https only).",
    )
    tender_fetch_allow_private_hosts: bool = Field(
        default=False,
        alias="TENDER_FETCH_ALLOW_PRIVATE_HOSTS",
        description="Allow resolving to RFC1918 / loopback (SSRF risk; dev only).",
    )
    tender_search_max_results: int = Field(
        default=24,
        ge=1,
        le=50,
        alias="TENDER_SEARCH_MAX_RESULTS",
        description="Max merged search hits (EIS + DDG) before enrichment; raise via env for broader assistant lists.",
    )
    tender_search_enrich_max_pages: int = Field(
        default=16,
        ge=0,
        le=50,
        alias="TENDER_SEARCH_ENRICH_MAX_PAGES",
        description="How many search result rows get OpenAI batch summary (0 = heuristic/snippet only).",
    )
    tender_search_enrich_with_ai: bool = Field(
        default=True,
        alias="TENDER_SEARCH_ENRICH_WITH_AI",
        description="Use OpenAI for Russian summaries when OPENAI_API_KEY is set.",
    )
    tender_search_enrich_concurrency: int = Field(
        default=3,
        ge=1,
        le=10,
        alias="TENDER_SEARCH_ENRICH_CONCURRENCY",
        description="Parallel tender page fetches during search enrichment.",
    )
    tender_search_only_open_deadlines: bool = Field(
        default=True,
        alias="TENDER_SEARCH_ONLY_OPEN_DEADLINES",
        description="When enriching search, drop tenders whose application deadline is before server UTC now.",
    )
    tender_search_exclude_unknown_deadline: bool = Field(
        default=False,
        alias="TENDER_SEARCH_EXCLUDE_UNKNOWN_DEADLINE",
        description=(
            "If true, drop enriched hits with no parsed submission deadline when only_open_deadlines is on. "
            "Default false so assistant lists match browser better (many cards lack a parsable date in automated fetch)."
        ),
    )
    tender_fetch_doh_fallback: bool = Field(
        default=True,
        alias="TENDER_FETCH_DOH_FALLBACK",
        description="If system DNS fails, resolve A via DNS-over-HTTPS (1.1.1.1) and fetch with curl --resolve.",
    )
    tender_zakupki_import_max_files: int = Field(
        default=25,
        ge=1,
        le=100,
        alias="TENDER_ZAKUPKI_IMPORT_MAX_FILES",
        description="Max public ЕИС filestore attachments to pull into MinIO per tender import.",
    )
    tender_zakupki_import_max_bytes_per_file: int = Field(
        default=50 * 1024 * 1024,
        ge=512_000,
        le=200 * 1024 * 1024,
        alias="TENDER_ZAKUPKI_IMPORT_MAX_BYTES_PER_FILE",
        description="Skip downloads larger than this (single attachment from zakupki filestore).",
    )

    # Optional ФГИС ЦС / pricing context for ``tender_smeta_service`` (see ``fgis_cs_client``).
    fgis_cs_context_json_url: str | None = Field(
        default=None,
        alias="FGIS_CS_CONTEXT_JSON_URL",
        description="HTTPS URL returning JSON/text with regional indices or notes for smeta prompts.",
    )
    fgis_cs_api_base_url: str | None = Field(
        default=None,
        alias="FGIS_CS_API_BASE_URL",
        description="Optional gateway base (no trailing slash); used with FGIS_CS_API_PATH.",
    )
    fgis_cs_api_path: str | None = Field(
        default=None,
        alias="FGIS_CS_API_PATH",
        description="Path appended to FGIS_CS_API_BASE_URL for organisation-specific pricing API.",
    )
    fgis_cs_api_token: str | None = Field(default=None, alias="FGIS_CS_API_TOKEN")
    fgis_cs_http_timeout_seconds: float = Field(
        default=15.0,
        ge=3.0,
        le=120.0,
        alias="FGIS_CS_HTTP_TIMEOUT_SECONDS",
    )

    # Multi-tenant testing: primary org for all users except Dev Admin; Dev Admin lists all companies.
    testing_company_name: str = Field(default="Спец-строй", alias="TESTING_COMPANY_NAME")
    testing_company_slug: str = Field(default="spec-stroy", alias="TESTING_COMPANY_SLUG")
    dev_admin_user_ids: list[str] = Field(default_factory=list, alias="DEV_ADMIN_USER_IDS")
    dev_admin_emails: list[str] = Field(default_factory=list, alias="DEV_ADMIN_EMAILS")

    @field_validator("dev_admin_user_ids", "dev_admin_emails", mode="before")
    @classmethod
    def parse_dev_admin_lists(cls, v: str | list[str] | None) -> list[str]:
        """Parse Dev Admin identifiers from JSON array or comma-separated string."""
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        raw = str(v).strip()
        if not raw:
            return []
        if raw.startswith("["):
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                return []
            return [str(x).strip() for x in parsed if str(x).strip()]
        return [x.strip() for x in raw.split(",") if x.strip()]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from JSON string or list."""
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("task_scheduler_observer_ids", "task_scheduler_co_assignee_ids", mode="before")
    @classmethod
    def parse_scheduler_uuid_list(cls, v: str | list[str] | None) -> list[str]:
        """Parse scheduler user id lists from JSON/CSV or pass-through list."""
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        raw = str(v).strip()
        if not raw:
            return []
        if raw.startswith("["):
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                return []
            return [str(x).strip() for x in parsed if str(x).strip()]
        return [x.strip() for x in raw.split(",") if x.strip()]

    def keycloak_expected_issuer(self) -> str:
        """Return JWT ``iss`` value for validating Keycloak access tokens."""
        custom = (self.keycloak_token_issuer or "").strip()
        if custom:
            return custom.rstrip("/")
        return f"{self.keycloak_url.rstrip('/')}/realms/{self.keycloak_realm}"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton.

    Возвращает:
        Экземпляр Settings, загруженный из окружения.
    """
    return Settings()  # type: ignore[call-arg]
