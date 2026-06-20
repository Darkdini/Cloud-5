"""Админ-панель донат-бота (только для владельца).

Доступна админам (telegram_id из settings.admin.ids или DEFAULT_ADMIN_IDS).
Позволяет менять суммы кнопок доната и смотреть статистику прямо в Telegram.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cloud5.core.filters import IsAdmin
from cloud5.core.menu import donate_amounts
from cloud5.core.registry import TenantInfo
from cloud5.core.tenant_settings import patch_module_settings
from cloud5.db.models import BotUser, Donation

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class SetDonate(StatesGroup):
    amount = State()


def _home_kb() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.button(text="💵 Суммы кнопок", callback_data="adm:donate")
    b.button(text="📊 Статистика", callback_data="adm:stats")
    b.adjust(1)
    return b


@router.message(Command("admin"))
async def admin_home_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=_home_kb().as_markup())


@router.callback_query(F.data == "adm:home")
async def admin_home_cb(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _edit(query, "⚙️ <b>Админ-панель</b>", _home_kb())


# --------------------------------------------------------------------------- #
# Донат
# --------------------------------------------------------------------------- #


@router.callback_query(F.data == "adm:donate")
async def donate_menu(query: CallbackQuery, tenant: TenantInfo) -> None:
    cfg = tenant.module_settings("donate")
    pretty = ", ".join(f"{a}⭐" for a in donate_amounts(tenant))
    wall = cfg.get("wall_chat_id")
    wall_txt = f"чат {wall}" if wall else "не задана"
    b = InlineKeyboardBuilder()
    b.button(text="💵 Изменить суммы кнопок", callback_data="adm:donate:amount")
    b.button(text="⬅️ Назад", callback_data="adm:home")
    b.adjust(1)
    await _edit(
        query,
        "💝 <b>Донат</b>\n"
        f"Кнопки сумм: <b>{pretty}</b>\n"
        f"Доска почёта: <b>{wall_txt}</b>\n\n"
        "Чтобы привязать Доску почёта — добавь бота в свою группу/канал "
        "администратором и отправь там команду <code>/setwall</code>.",
        b,
    )


@router.callback_query(F.data == "adm:donate:amount")
async def donate_amount_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetDonate.amount)
    await _edit(
        query,
        "Введите суммы кнопок в звёздах через запятую,\n"
        "например: <code>100,200,300,400,1000</code>",
        _cancel_kb(),
    )


@router.message(SetDonate.amount, F.text)
async def donate_amount_save(
    message: Message, tenant: TenantInfo, session: AsyncSession, state: FSMContext
) -> None:
    amounts = []
    for part in (message.text or "").replace(" ", "").split(","):
        if part.isdigit() and int(part) >= 1:
            amounts.append(int(part))
    if not amounts:
        await message.answer("Введите числа через запятую, например 100,200,1000:")
        return
    await state.clear()
    await patch_module_settings(
        session, tenant, "donate", {"amounts": amounts, "amount_xtr": amounts[0]}
    )
    pretty = ", ".join(f"{a}⭐" for a in amounts)
    await message.answer(
        f"✅ Суммы кнопок: {pretty}.\nОтправьте /start, чтобы обновить меню.",
        reply_markup=_back_kb("adm:donate").as_markup(),
    )


# --------------------------------------------------------------------------- #
# Статистика
# --------------------------------------------------------------------------- #


@router.callback_query(F.data == "adm:stats")
async def stats(query: CallbackQuery, tenant: TenantInfo, session: AsyncSession) -> None:
    users = await session.scalar(
        select(func.count()).select_from(BotUser).where(BotUser.tenant_id == tenant.id)
    )
    donations = await session.scalar(
        select(func.count()).select_from(Donation).where(Donation.tenant_id == tenant.id)
    )
    stars = await session.scalar(
        select(func.coalesce(func.sum(Donation.amount_xtr), 0)).where(
            Donation.tenant_id == tenant.id
        )
    )
    await _edit(
        query,
        "📊 <b>Статистика</b>\n"
        f"👥 Пользователей: {users or 0}\n"
        f"🎁 Донатов: {donations or 0}\n"
        f"⭐ Собрано звёзд: {stars or 0}",
        _back_kb("adm:home"),
    )


# --------------------------------------------------------------------------- #
# Помощники
# --------------------------------------------------------------------------- #


def _cancel_kb() -> InlineKeyboardBuilder:
    return _back_kb("adm:home", text="✖️ Отмена")


def _back_kb(target: str, text: str = "⬅️ Назад") -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.button(text=text, callback_data=target)
    return b


async def _edit(query: CallbackQuery, text: str, builder: InlineKeyboardBuilder) -> None:
    if isinstance(query.message, Message):
        try:
            await query.message.edit_text(text, reply_markup=builder.as_markup())
        except Exception:  # noqa: BLE001
            await query.message.answer(text, reply_markup=builder.as_markup())
    await query.answer()
