"""Модуль поддержки: создание тикета и уведомление операторов."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from cloud5.core.filters import ModuleEnabled
from cloud5.core.logging import get_logger
from cloud5.core.menu import back_to_menu_button
from cloud5.core.registry import TenantInfo
from cloud5.db.models import BotUser, Ticket, TicketMessage, TicketStatus

log = get_logger("support")

router = Router(name="support")
router.callback_query.filter(ModuleEnabled("support"))
router.message.filter(ModuleEnabled("support"))


class SupportFlow(StatesGroup):
    describing = State()


@router.callback_query(F.data == "support:new")
async def support_new(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportFlow.describing)
    builder = InlineKeyboardBuilder()
    builder.add(back_to_menu_button())
    if isinstance(query.message, Message):
        await query.message.edit_text(
            "🎫 Опишите ваш вопрос или проблему одним сообщением — "
            "оператор скоро ответит.",
            reply_markup=builder.as_markup(),
        )
    await query.answer()


@router.message(SupportFlow.describing, F.text)
async def support_create(
    message: Message,
    tenant: TenantInfo,
    user: BotUser,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    await state.clear()

    ticket = Ticket(
        tenant_id=tenant.id,
        user_id=user.id,
        subject=text[:120],
        status=TicketStatus.open,
        messages=[TicketMessage(from_operator=False, content=text)],
    )
    session.add(ticket)
    await session.flush()

    await _notify_operators(message, tenant, user, ticket, text)

    builder = InlineKeyboardBuilder()
    builder.add(back_to_menu_button())
    await message.answer(
        f"✅ Заявка #{ticket.id} создана. Мы свяжемся с вами в ближайшее время!",
        reply_markup=builder.as_markup(),
    )


async def _notify_operators(
    message: Message,
    tenant: TenantInfo,
    user: BotUser,
    ticket: Ticket,
    text: str,
) -> None:
    chat_id = tenant.module_settings("support").get("operator_chat_id")
    if not chat_id:
        return
    handle = f"@{user.username}" if user.username else f"id{user.telegram_id}"
    try:
        await message.bot.send_message(
            chat_id,
            f"🎫 <b>Новая заявка #{ticket.id}</b>\n"
            f"От: {user.full_name} ({handle})\n\n"
            f"{text}",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("operator_notify_failed", error=str(exc))
