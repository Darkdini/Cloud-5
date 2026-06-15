"""Работа с пользователями ботов (get-or-create, обновление профиля)."""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram.types import User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloud5.db.models import BotUser


async def get_or_create_user(
    session: AsyncSession, tenant_id: int, tg_user: TgUser
) -> BotUser:
    """Найти пользователя бота или создать, попутно обновив профиль."""
    user = (
        await session.execute(
            select(BotUser).where(
                BotUser.tenant_id == tenant_id,
                BotUser.telegram_id == tg_user.id,
            )
        )
    ).scalar_one_or_none()

    if user is None:
        user = BotUser(
            tenant_id=tenant_id,
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            locale=tg_user.language_code,
        )
        session.add(user)

    user.username = tg_user.username
    user.first_name = tg_user.first_name
    user.last_name = tg_user.last_name
    user.last_seen_at = datetime.now(UTC)
    await session.flush()
    return user
