"""Модули донат-бота.

Каждый модуль экспортирует ``router`` (aiogram Router). Регистрация роутеров — в
:func:`register_modules`.
"""

from __future__ import annotations

from aiogram import Dispatcher

from cloud5.modules import admin, common, donate


def register_modules(dp: Dispatcher) -> None:
    # admin — раньше всех: /admin и адм-команды владельца имеют приоритет
    dp.include_router(admin.router)
    # common — навигация по меню (/start)
    dp.include_router(common.router)
    dp.include_router(donate.router)
