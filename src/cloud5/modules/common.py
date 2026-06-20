"""Общий модуль: /start, главное меню (reply-кнопки сумм доната)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from cloud5.core.menu import donate_amount_for_label, main_reply_menu
from cloud5.core.registry import TenantInfo
from cloud5.modules import donate

router = Router(name="common")


async def _is_donate_button(
    message: Message, tenant: TenantInfo | None = None
) -> bool:
    """Фильтр: текст совпал с одной из кнопок-сумм доната."""
    if tenant is None or not message.text:
        return False
    return donate_amount_for_label(tenant, message.text) is not None


def _greeting(tenant: TenantInfo) -> str:
    custom = tenant.module_settings("common").get("greeting")
    if custom:
        return custom
    return (
        f"👋 Привет! Это бот «{tenant.title}».\n\n"
        "Поддержи проект звёздами — выбери сумму ниже 👇"
    )


@router.message(Command("start"))
async def cmd_start(message: Message, tenant: TenantInfo, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_greeting(tenant), reply_markup=main_reply_menu(tenant))


@router.message(Command("menu"))
async def cmd_menu(message: Message, tenant: TenantInfo, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Выбери сумму доната 👇", reply_markup=main_reply_menu(tenant))


@router.message(_is_donate_button)
async def on_donate_button(
    message: Message, tenant: TenantInfo, state: FSMContext
) -> None:
    """Нажата кнопка-сумма — выставить счёт на эту сумму."""
    amount = donate_amount_for_label(tenant, message.text or "")
    if amount is None:
        return
    await state.clear()
    await donate.donate_start(message, tenant, amount)


@router.callback_query(F.data == "menu:home")
async def cb_home(query: CallbackQuery, tenant: TenantInfo, state: FSMContext) -> None:
    await state.clear()
    if isinstance(query.message, Message):
        try:
            await query.message.edit_text("Выбери сумму доната 👇")
        except Exception:  # noqa: BLE001
            pass
    await query.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/start — показать кнопки доната\n"
        "/menu — меню"
    )
