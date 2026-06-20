"""Сборка главного меню бота по списку включённых модулей."""

from __future__ import annotations

from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from cloud5.core.registry import TenantInfo

# module -> (надпись кнопки, callback_data)
MENU_ITEMS: dict[str, tuple[str, str]] = {
    "ai_assistant": ("🧠 Задать вопрос", "ai:start"),
    "shop": ("🛒 Магазин", "shop:catalog"),
    "booking": ("📅 Записаться", "booking:services"),
    "support": ("🎫 Поддержка", "support:new"),
    "donate": ("⭐ Поддержать", "donate:start"),
}

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


def menu_label(module: str, tenant: TenantInfo) -> str:
    """Подпись кнопки меню. Для доната — динамическая с суммой звёзд."""
    if module == "donate":
        cfg = tenant.module_settings("donate")
        try:
            amount = max(1, int(cfg.get("amount_xtr", 2)))
        except (TypeError, ValueError):
            amount = 2
        return f"⭐ Подарить {amount} {_plural_star(amount)}"
    item = MENU_ITEMS.get(module)
    return item[0] if item else module


def module_for_label(tenant: TenantInfo, text: str) -> str | None:
    """Найти модуль по тексту нажатой reply-кнопки (учёт динамических подписей)."""
    for module in tenant.enabled_modules:
        if module in MENU_ITEMS and menu_label(module, tenant) == text:
            return module
    return None


def main_reply_menu(tenant: TenantInfo) -> ReplyKeyboardMarkup:
    """Постоянное reply-меню снизу экрана — кнопки во всю ширину."""
    builder = ReplyKeyboardBuilder()
    for module in tenant.enabled_modules:
        if module in MENU_ITEMS:
            builder.add(KeyboardButton(text=menu_label(module, tenant)))
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


# Неразрывный пробел: обычные пробелы по краям Telegram обрезает, этот — нет.
NBSP = " "


def center_label(text: str, width: int) -> str:
    """Выровнять подпись кнопки по центру, добив неразрывными пробелами до ``width``.

    Telegram ужимает inline-кнопки по ширине текста, прижимает к левому краю и
    срезает обычные пробелы по краям. Неразрывный пробел не срезается — кнопки
    получаются одинаковой ширины, а текст смотрится по центру.
    """
    return text.center(max(width, len(text)), NBSP)


def main_menu(tenant: TenantInfo) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    items = [
        (menu_label(m, tenant), MENU_ITEMS[m][1])
        for m in tenant.enabled_modules
        if m in MENU_ITEMS
    ]
    width = max((len(text) for text, _ in items), default=0)
    width = max(width, 22)
    for text, data in items:
        builder.add(
            InlineKeyboardButton(
                text=center_label(text, width), callback_data=data
            )
        )
    builder.adjust(1)
    return builder.as_markup()


def back_to_menu_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="⬅️ В меню", callback_data="menu:home")
