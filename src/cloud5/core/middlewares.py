"""Middleware: привязка тенанта, БД-сессии и пользователя к каждому апдейту."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from cloud5.core.logging import get_logger
from cloud5.core.registry import registry
from cloud5.core.users import get_or_create_user
from cloud5.db.session import session_scope

log = get_logger("middleware")


class TenantMiddleware(BaseMiddleware):
    """Определяет тенанта по токену бота, открывает транзакцию и грузит юзера.

    В data попадают: ``tenant`` (TenantInfo), ``session`` (AsyncSession),
    ``user`` (BotUser | None).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        bot = data["bot"]
        tenant = registry.by_token(bot.token)
        if tenant is None:
            log.warning("unknown_bot_token", bot_id=getattr(bot, "id", None))
            return None

        tg_user = data.get("event_from_user")
        async with session_scope() as session:
            data["tenant"] = tenant
            data["session"] = session
            data["user"] = (
                await get_or_create_user(session, tenant.id, tg_user)
                if tg_user is not None
                else None
            )
            return await handler(event, data)
