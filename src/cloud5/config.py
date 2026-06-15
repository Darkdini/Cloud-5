"""Глобальные настройки платформы (читаются из окружения / .env)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # База данных и кэш
    database_url: str = "postgresql+asyncpg://cloud5:cloud5@localhost:5432/cloud5"
    redis_url: str = "redis://localhost:6379/0"

    # ИИ
    anthropic_api_key: str = ""
    ai_model: str = "claude-sonnet-4-6"

    # Режим запуска ботов
    bot_mode: str = "polling"  # polling | webhook
    webhook_base_url: str = ""
    webhook_secret: str = "change-me"

    # Админ-API
    admin_api_token: str = "change-me-admin-token"

    # Прочее
    log_level: str = "INFO"
    default_locale: str = "ru"

    @property
    def sync_database_url(self) -> str:
        """URL для Alembic (синхронный драйвер)."""
        return self.database_url.replace("+asyncpg", "+psycopg2").replace(
            "postgresql+", "postgresql+", 1
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
