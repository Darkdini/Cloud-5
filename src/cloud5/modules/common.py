"""Общий модуль: /start, главное меню, навигация."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from cloud5.core.menu import main_menu
from cloud5.core.registry import TenantInfo

router = Router(name="common")


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
    await message.answer(_greeting(tenant), reply_markup=main_menu(tenant))


@router.message(Command("menu"))
async def cmd_menu(message: Message, tenant: TenantInfo, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu(tenant))


@router.callback_query(F.data == "menu:home")
async def cb_home(query: CallbackQuery, tenant: TenantInfo, state: FSMContext) -> None:
    await state.clear()
    if isinstance(query.message, Message):
        await query.message.edit_text(
            "Главное меню:", reply_markup=main_menu(tenant)
        )
    await query.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/start — начать\n"
        "/menu — главное меню\n"
        "/help — помощь"
    )
