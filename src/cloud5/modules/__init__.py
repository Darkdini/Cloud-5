"""Бизнес-модули платформы.

Каждый модуль экспортирует ``router`` (aiogram Router). Регистрация всех роутеров
происходит в :func:`register_modules`. Гейтинг по включённым модулям выполняется
фильтром :class:`cloud5.core.filters.ModuleEnabled` внутри самих роутеров.
"""

from __future__ import annotations

from aiogram import Dispatcher

from cloud5.modules import ai_assistant, booking, common, shop, support


def register_modules(dp: Dispatcher) -> None:
    # common — всегда первым (/start, навигация по меню)
    dp.include_router(common.router)
    dp.include_router(ai_assistant.router)
    dp.include_router(shop.router)
    dp.include_router(booking.router)
    dp.include_router(support.router)
