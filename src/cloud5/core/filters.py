"""Кастомные фильтры aiogram."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
from aiogram.types import User as TgUser

from cloud5.core.registry import TenantInfo
from cloud5.core.tenant_settings import is_admin


class ModuleEnabled(BaseFilter):
    """Пропускает апдейт только если у тенанта включён нужный модуль."""

    def __init__(self, module: str) -> None:
        self.module = module

    async def __call__(
        self, event: TelegramObject, tenant: TenantInfo | None = None
    ) -> bool:
        return tenant is not None and tenant.has_module(self.module)


class IsAdmin(BaseFilter):
    """Пропускает апдейт только от админа бота (telegram_id в settings.admin.ids)."""

    async def __call__(
        self,
        event: TelegramObject,
        tenant: TenantInfo | None = None,
        event_from_user: TgUser | None = None,
    ) -> bool:
        if tenant is None or event_from_user is None:
            return False
        return is_admin(tenant, event_from_user.id)
