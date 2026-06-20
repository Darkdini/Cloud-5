"""Донаты на Telegram Stars + «Доска почёта» спонсоров.

Пользователь жмёт кнопку и дарит ⭐. После оплаты бот:
- записывает донат и благодарит спонсора;
- публикует красивую карточку спонсора в группе/канале «Доска почёта»
  (настраивается командой /setwall прямо в этом чате).
"""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cloud5.core.filters import IsAdmin
from cloud5.core.logging import get_logger
from cloud5.core.menu import back_to_menu_button
from cloud5.core.registry import TenantInfo
from cloud5.core.tenant_settings import patch_module_settings
from cloud5.db.models import BotUser, Donation
from cloud5.services.card import render_donor_card

router = Router(name="donate")
log = get_logger("donate")

DEFAULT_AMOUNT = 2


def _cfg(tenant: TenantInfo) -> dict:
    return tenant.module_settings("donate")


def _amount(tenant: TenantInfo) -> int:
    try:
        return max(1, int(_cfg(tenant).get("amount_xtr", DEFAULT_AMOUNT)))
    except (TypeError, ValueError):
        return DEFAULT_AMOUNT


def _mention(user: BotUser) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name


# --------------------------------------------------------------------------- #
# Кнопка доната и инвойс
# --------------------------------------------------------------------------- #


@router.callback_query(F.data == "donate:start")
async def donate_start(
    query: CallbackQuery | Message,
    tenant: TenantInfo,
    amount: int | None = None,
) -> None:
    amount = amount or _amount(tenant)
    target = query.message if isinstance(query, CallbackQuery) else query
    if not isinstance(target, Message):
        if isinstance(query, CallbackQuery):
            await query.answer()
        return
    await target.answer_invoice(
        title="Поддержать проект",
        description=f"Подарить {amount} ⭐ автору. Спасибо за поддержку!",
        payload=f"donate:{amount}",
        provider_token="",  # для Stars токен пустой
        currency="XTR",
        prices=[LabeledPrice(label=f"Донат {amount} ⭐", amount=amount)],
    )
    if isinstance(query, CallbackQuery):
        await query.answer()


@router.callback_query(F.data == "donate:wall")
async def donate_wall(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    await _show_wall(query, tenant, session)


# --------------------------------------------------------------------------- #
# Оплата
# --------------------------------------------------------------------------- #


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    await pre_checkout_query.answer(ok=True)


@router.message(
    F.successful_payment.func(
        lambda p: p is not None and p.invoice_payload.startswith("donate:")
    )
)
async def on_donated(
    message: Message, tenant: TenantInfo, user: BotUser, session: AsyncSession
) -> None:
    sp = message.successful_payment
    amount = sp.total_amount  # для XTR это число звёзд
    donation = Donation(
        tenant_id=tenant.id,
        user_id=user.id,
        amount_xtr=amount,
        charge_id=sp.telegram_payment_charge_id,
    )
    session.add(donation)
    await session.flush()

    # благодарность спонсору
    b = InlineKeyboardBuilder()
    b.button(text="🏆 Доска почёта", callback_data="donate:wall")
    b.button(text="⭐ Подарить ещё", callback_data="donate:start")
    b.adjust(1)
    await message.answer(
        f"💖 Спасибо за поддержку, {_mention(user)}!\n"
        f"Твой вклад: {amount} ⭐ — ты теперь в Доске почёта.",
        reply_markup=b.as_markup(),
    )

    # публикация в группу/канал «Доска почёта»
    wall_chat = _cfg(tenant).get("wall_chat_id")
    if wall_chat:
        try:
            await _publish_card(message.bot, wall_chat, user, amount)
            donation.posted = True
            await session.flush()
        except Exception as exc:  # noqa: BLE001
            log.warning("wall_post_failed", error=str(exc), chat=wall_chat)


async def _publish_card(bot: Bot, chat_id: int, user: BotUser, amount: int) -> None:
    """Опубликовать карточку донатера: картинкой, либо текстом (если нет Pillow)."""
    image = render_donor_card(_mention(user), amount)
    if image is not None:
        await bot.send_photo(
            chat_id,
            BufferedInputFile(image, filename="donor.png"),
            caption=f"🏅 <b>{_mention(user)}</b> поддержал на {amount} ⭐. Спасибо! ❤️",
        )
    else:
        await bot.send_message(chat_id, _wall_card(user, amount))


@router.message(Command("testdonate"), IsAdmin())
async def test_donate(
    message: Message, tenant: TenantInfo, user: BotUser
) -> None:
    """Тестовая «покупка» для админа: показывает карточку без реальной оплаты."""
    amount = _amount(tenant)
    # показать карточку самому админу
    await _publish_card(message.bot, message.chat.id, user, amount)
    wall_chat = _cfg(tenant).get("wall_chat_id")
    if not wall_chat:
        await message.answer(
            "ℹ️ Это тест карточки. Группа-доска не привязана — "
            "добавь бота в группу админом и отправь там /setwall."
        )
        return
    try:
        await _publish_card(message.bot, wall_chat, user, amount)
        await message.answer("✅ Тест: карточка отправлена в группу-доску.")
    except Exception as exc:  # noqa: BLE001
        await message.answer(
            f"⚠️ Не смог отправить в группу: {exc}\n"
            "Проверь, что бот — администратор группы и там выполнен /setwall."
        )


# --------------------------------------------------------------------------- #
# Настройка доски (команда в нужном чате)
# --------------------------------------------------------------------------- #


@router.message(Command("setwall"), IsAdmin())
async def set_wall(
    message: Message, tenant: TenantInfo, session: AsyncSession
) -> None:
    chat_id = message.chat.id
    await patch_module_settings(session, tenant, "donate", {"wall_chat_id": chat_id})
    await message.answer(
        "✅ Доска почёта привязана к этому чату.\n"
        f"<code>chat_id = {chat_id}</code>\n"
        "Теперь сюда будут падать карточки спонсоров. "
        "Убедись, что бот — администратор этого чата."
    )


@router.message(Command("unsetwall"), IsAdmin())
async def unset_wall(
    message: Message, tenant: TenantInfo, session: AsyncSession
) -> None:
    await patch_module_settings(session, tenant, "donate", {"wall_chat_id": None})
    await message.answer("✅ Публикация в Доску почёта отключена.")


# --------------------------------------------------------------------------- #
# Доска почёта внутри бота
# --------------------------------------------------------------------------- #


async def _show_wall(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    total = await session.scalar(
        select(func.coalesce(func.sum(Donation.amount_xtr), 0)).where(
            Donation.tenant_id == tenant.id
        )
    )
    count = await session.scalar(
        select(func.count()).select_from(Donation).where(
            Donation.tenant_id == tenant.id
        )
    )
    rows = (
        await session.execute(
            select(Donation, BotUser)
            .join(BotUser, BotUser.id == Donation.user_id)
            .where(Donation.tenant_id == tenant.id)
            .order_by(Donation.id.desc())
            .limit(15)
        )
    ).all()

    lines = ["🏆 <b>Доска почёта</b>", ""]
    if rows:
        for don, usr in rows:
            lines.append(f"🏅 {_mention(usr)} — {don.amount_xtr} ⭐")
        lines.append("")
        lines.append(f"Всего: <b>{total} ⭐</b> от {count} спонсоров. Спасибо! 💖")
    else:
        lines.append("Пока пусто — стань первым спонсором! ✨")

    b = InlineKeyboardBuilder()
    b.button(text="⭐ Подарить звёзды", callback_data="donate:start")
    b.add(back_to_menu_button())
    b.adjust(1)
    text = "\n".join(lines)
    if isinstance(query.message, Message):
        try:
            await query.message.edit_text(text, reply_markup=b.as_markup())
        except Exception:  # noqa: BLE001
            await query.message.answer(text, reply_markup=b.as_markup())
    await query.answer()


# --------------------------------------------------------------------------- #
# Помощники
# --------------------------------------------------------------------------- #


def _wall_card(user: BotUser, amount: int) -> str:
    """Красивая текстовая карточка спонсора для публикации в группе."""
    deco = "✨🌟" * 6
    return (
        f"{deco}\n"
        "🏆 <b>НОВЫЙ СПОНСОР!</b> 🏆\n\n"
        f"🏅 <b>{_mention(user)}</b>\n"
        f"💝 поддержал на <b>{amount} ⭐</b>\n\n"
        "Спасибо за поддержку! ❤️\n"
        f"{deco}"
    )
