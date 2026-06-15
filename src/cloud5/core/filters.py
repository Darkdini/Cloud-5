"""Кастомные фильтры aiogram."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from cloud5.core.registry import TenantInfo


class ModuleEnabled(BaseFilter):
    """Пропускает апдейт только если у тенанта включён нужный модуль."""

    def __init__(self, module: str) -> None:
        self.module = module

    async def __call__(
        self, event: TelegramObject, tenant: TenantInfo | None = None
    ) -> bool:
        return tenant is not None and tenant.has_module(self.module)
