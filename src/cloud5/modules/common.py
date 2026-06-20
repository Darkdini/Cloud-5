"""Общий модуль: /start, главное меню (reply), навигация."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from cloud5.core.menu import main_reply_menu, module_for_label
from cloud5.core.registry import TenantInfo
from cloud5.modules import ai_assistant, booking, donate, shop, support

router = Router(name="common")


async def _is_menu_label(
    message: Message, tenant: TenantInfo | None = None
) -> bool:
    """Фильтр: текст совпадает с подписью одной из кнопок меню тенанта."""
    if tenant is None or not message.text:
        return False
    return module_for_label(tenant, message.text) is not None


def _greeting(tenant: TenantInfo) -> str:
    custom = tenant.module_settings("common").get("greeting")
    if custom:
        return custom
    return (
        f"👋 Здравствуйте! Это бот «{tenant.title}».\n\n"
        "Выберите, что вас интересует:"
    )


@router.message(Command("start"))
async def cmd_start(message: Message, tenant: TenantInfo, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_greeting(tenant), reply_markup=main_reply_menu(tenant))


@router.message(Command("menu"))
async def cmd_menu(message: Message, tenant: TenantInfo, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню 👇", reply_markup=main_reply_menu(tenant))


@router.message(_is_menu_label)
async def on_menu_text(
    message: Message,
    tenant: TenantInfo,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Нажатие кнопки reply-меню — открыть соответствующий раздел."""
    module = module_for_label(tenant, message.text or "")
    if module is None:
        return
    await state.clear()
    if module == "shop":
        await shop.catalog(message, tenant, session)
    elif module == "booking":
        await booking.services(message, tenant, session)
    elif module == "support":
        await support.support_new(message, state)
    elif module == "ai_assistant":
        await ai_assistant.ai_start(message, state)
    elif module == "donate":
        await donate.donate_start(message, tenant)


@router.callback_query(F.data == "menu:home")
async def cb_home(query: CallbackQuery, tenant: TenantInfo, state: FSMContext) -> None:
    await state.clear()
    if isinstance(query.message, Message):
        try:
            await query.message.edit_text("Главное меню 👇")
        except Exception:  # noqa: BLE001
            pass
    await query.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/start — начать\n"
        "/menu — главное меню\n"
        "/help — помощь"
    )
