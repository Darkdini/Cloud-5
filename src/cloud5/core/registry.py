"""Реестр тенантов: загрузка активных ботов из БД и сопоставление токенов."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select

from cloud5.db.models import Tenant
from cloud5.db.session import session_scope


@dataclass
class TenantInfo:
    """Лёгкая копия данных тенанта для использования в рантайме."""

    id: int
    title: str
    bot_token: str
    bot_username: str | None
    locale: str
    enabled_modules: list[str] = field(default_factory=list)
    settings: dict = field(default_factory=dict)

    def has_module(self, module: str) -> bool:
        return module in self.enabled_modules

    def module_settings(self, module: str) -> dict:
        return (self.settings or {}).get(module, {})


class TenantRegistry:
    """Держит в памяти активные тенанты и индекс по токену."""

    def __init__(self) -> None:
        self._by_token: dict[str, TenantInfo] = {}

    async def load(self) -> list[TenantInfo]:
        async with session_scope() as session:
            rows = (
                await session.execute(
                    select(Tenant).where(Tenant.is_active.is_(True))
                )
            ).scalars().all()
        self._by_token = {
            t.bot_token: TenantInfo(
                id=t.id,
                title=t.title,
                bot_token=t.bot_token,
                bot_username=t.bot_username,
                locale=t.locale,
                enabled_modules=list(t.enabled_modules or []),
                settings=dict(t.settings or {}),
            )
            for t in rows
        }
        return list(self._by_token.values())

    def by_token(self, token: str) -> TenantInfo | None:
        return self._by_token.get(token)

    @property
    def tokens(self) -> list[str]:
        return list(self._by_token.keys())


registry = TenantRegistry()
