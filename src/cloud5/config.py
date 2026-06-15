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

    # База данных и кэш.
    # По умолчанию — SQLite (работает на телефоне без сервера). Для продакшена
    # переопределите DATABASE_URL/REDIS_URL в окружении (см. docker-compose.yml).
    database_url: str = "sqlite+aiosqlite:///./cloud5.db"
    redis_url: str = ""

    # ИИ
    anthropic_api_key: str = ""
    ai_model: str = "claude-sonnet-4-6"

    # Тестовый бот по умолчанию (для команды quickstart).
    # ВНИМАНИЕ: токен виден в репозитории — после тестов отзовите его у @BotFather.
    default_bot_token: str = "8753886936:AAHG9I2XX3UemhkO0BnmsMKUerw54ZHiz3w"
    default_bot_title: str = "Мой бизнес"
    default_modules: str = "shop,booking,support"

    # Режим запуска ботов
    bot_mode: str = "polling"  # polling | webhook
    webhook_base_url: str = ""
    webhook_secret: str = "change-me"

    # Админ-API
    admin_api_token: str = "change-me-admin-token"

    # Прочее
    log_level: str = "INFO"
    default_locale: str = "ru"

    # Глобальные админы (через запятую). Имеют доступ к /admin во всех ботах
    # и автоматически добавляются новым тенантам.
    default_admin_ids: str = "7164355388"

    @property
    def admin_ids_list(self) -> list[int]:
        out: list[int] = []
        for part in self.default_admin_ids.split(","):
            part = part.strip()
            if part.isdigit():
                out.append(int(part))
        return out

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
