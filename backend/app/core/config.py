"""Application configuration loaded from environment variables.

Использует pydantic-settings для валидации и загрузки конфигурации
из переменных окружения или .env файла.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "HVAC CRM/ERP Platform"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, alias="BACKEND_DEBUG")
    secret_key: str = "change-me"
    log_level: str = "INFO"

    database_url: str
    database_url_sync: str = ""
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_secret"
    minio_bucket: str = "hvac-documents"

    keycloak_url: str = "http://keycloak:8080"
    keycloak_realm: str = "hvac"
    keycloak_client_id: str = "hvac-backend"
    keycloak_client_secret: str = "backend-secret-change-me"

    cors_origins: list[str] = ["http://localhost:3000"]
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001

    telegram_bot_token: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from JSON string or list."""
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton.

    Возвращает:
        Экземпляр Settings, загруженный из окружения.
    """
    return Settings()  # type: ignore[call-arg]
