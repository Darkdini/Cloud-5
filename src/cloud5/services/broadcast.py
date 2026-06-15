"""Сервис массовых рассылок (CRM).

Отправляет сообщение всем пользователям тенанта, попадающим под сегмент,
с учётом лимитов Telegram (≈30 сообщений/сек) и фиксацией результата в БД.
"""

from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select

from cloud5.core.logging import get_logger
from cloud5.db.models import BotUser, Broadcast, BroadcastStatus, Order, Tenant
from cloud5.db.session import session_scope

log = get_logger("broadcast")

# Безопасный темп: ~25 сообщений в секунду
SEND_DELAY = 0.04


async def _segment_user_ids(session, tenant_id: int, segment: dict) -> list[int]:
    stmt = select(BotUser.telegram_id).where(
        BotUser.tenant_id == tenant_id,
        BotUser.is_blocked.is_(False),
    )
    if segment.get("has_order"):
        stmt = stmt.where(
            BotUser.id.in_(
                select(Order.user_id).where(Order.tenant_id == tenant_id)
            )
        )
    return list((await session.execute(stmt)).scalars().all())


async def run_broadcast(broadcast_id: int) -> dict:
    """Выполнить рассылку. Возвращает сводку {sent, failed}."""
    async with session_scope() as session:
        broadcast = await session.get(Broadcast, broadcast_id)
        if broadcast is None:
            raise ValueError(f"broadcast {broadcast_id} not found")
        tenant = await session.get(Tenant, broadcast.tenant_id)
        if tenant is None:
            raise ValueError("tenant not found")

        broadcast.status = BroadcastStatus.sending
        await session.flush()

        user_ids = await _segment_user_ids(session, tenant.id, broadcast.segment or {})
        text = broadcast.text
        photo = broadcast.photo_url
        token = tenant.bot_token

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    sent = failed = 0
    try:
        for tg_id in user_ids:
            try:
                if photo:
                    await bot.send_photo(tg_id, photo, caption=text)
                else:
                    await bot.send_message(tg_id, text)
                sent += 1
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after)
                continue
            except TelegramForbiddenError:
                failed += 1  # пользователь заблокировал бота
            except Exception as exc:  # noqa: BLE001
                failed += 1
                log.warning("broadcast_send_failed", tg_id=tg_id, error=str(exc))
            await asyncio.sleep(SEND_DELAY)
    finally:
        await bot.session.close()

    async with session_scope() as session:
        broadcast = await session.get(Broadcast, broadcast_id)
        if broadcast is not None:
            broadcast.status = BroadcastStatus.done
            broadcast.sent_count = sent
            broadcast.failed_count = failed

    log.info("broadcast_done", broadcast_id=broadcast_id, sent=sent, failed=failed)
    return {"sent": sent, "failed": failed}
