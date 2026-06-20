"""Меню донат-бота: reply-кнопки с суммами в звёздах."""

from __future__ import annotations

from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from cloud5.core.registry import TenantInfo

DEFAULT_DONATE_AMOUNTS = [100, 200, 300, 400, 1000]


def _plural_star(n: int) -> str:
    """Русское склонение слова «звезда» для числа n."""
    tail = abs(n) % 100
    if 11 <= tail <= 14:
        return "звёзд"
    d = tail % 10
    if d == 1:
        return "звезда"
    if 2 <= d <= 4:
        return "звезды"
    return "звёзд"


def donate_amounts(tenant: TenantInfo) -> list[int]:
    """Список сумм доната (в звёздах) — по кнопке на сумму."""
    cfg = tenant.module_settings("donate")
    raw = cfg.get("amounts")
    if raw:
        out = []
        for a in raw:
            try:
                v = int(a)
            except (TypeError, ValueError):
                continue
            if v >= 1:
                out.append(v)
        if out:
            return out
    # обратная совместимость: одиночная сумма
    try:
        return [max(1, int(cfg.get("amount_xtr", 100)))]
    except (TypeError, ValueError):
        return [100]


def donate_label(n: int, top: bool = False) -> str:
    """Подпись кнопки доната на сумму n. ``top`` — отметить как топовую."""
    if top:
        return f"🔥 {n} {_plural_star(n)} (ТОП)"
    return f"⭐ {n} {_plural_star(n)}"


def donate_amount_for_label(tenant: TenantInfo, text: str) -> int | None:
    """Вернуть сумму, если текст совпал с одной из донат-кнопок."""
    amounts = donate_amounts(tenant)
    top = max(amounts) if amounts else None
    for n in amounts:
        if donate_label(n, n == top) == text:
            return n
    return None


def main_reply_menu(tenant: TenantInfo) -> ReplyKeyboardMarkup:
    """Постоянное reply-меню снизу экрана — кнопки сумм во всю ширину."""
    builder = ReplyKeyboardBuilder()
    amounts = donate_amounts(tenant)
    top = max(amounts) if amounts else None
    for n in amounts:
        builder.add(KeyboardButton(text=donate_label(n, n == top)))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, is_persistent=True)


async def respond(event: Message | CallbackQuery, text: str, markup=None) -> None:
    """Показать экран: для нажатия inline — редактируем, для текста — новое сообщение."""
    if isinstance(event, CallbackQuery):
        if isinstance(event.message, Message):
            try:
                await event.message.edit_text(text, reply_markup=markup)
            except Exception:  # noqa: BLE001
                await event.message.answer(text, reply_markup=markup)
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup)


def back_to_menu_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:home")
