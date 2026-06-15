"""Мульти-тенантный рантайм: один Dispatcher обслуживает множество ботов."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from cloud5.config import settings
from cloud5.core.logging import get_logger
from cloud5.core.middlewares import TenantMiddleware
from cloud5.core.registry import registry
from cloud5.db.session import init_engine
from cloud5.modules import register_modules

log = get_logger("runtime")


def build_dispatcher() -> Dispatcher:
    # Пустой REDIS_URL → работаем на памяти (удобно для телефона/Termux)
    if not settings.redis_url:
        storage: RedisStorage | MemoryStorage = MemoryStorage()
    else:
        try:
            storage = RedisStorage.from_url(settings.redis_url)
        except Exception as exc:  # noqa: BLE001 — fallback на память
            log.warning("redis_unavailable_use_memory", error=str(exc))
            storage = MemoryStorage()

    dp = Dispatcher(storage=storage)
    # outer-middleware: после встроенного UserContextMiddleware (event_from_user готов)
    dp.update.outer_middleware(TenantMiddleware())
    register_modules(dp)
    return dp


def _make_bot(token: str) -> Bot:
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def run_polling() -> None:
    """Запустить всех активных ботов в режиме long polling."""
    init_engine()
    tenants = await registry.load()
    if not tenants:
        log.warning("no_active_tenants")
        return

    bots = [_make_bot(t.bot_token) for t in tenants]
    dp = build_dispatcher()
    log.info("starting_polling", bots=len(bots))
    await dp.start_polling(*bots, handle_signals=True)
