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

# обратная карта: надпись reply-кнопки -> модуль
LABEL_TO_MODULE: dict[str, str] = {text: m for m, (text, _) in MENU_ITEMS.items()}


def main_reply_menu(tenant: TenantInfo) -> ReplyKeyboardMarkup:
    """Постоянное reply-меню снизу экрана — кнопки во всю ширину."""
    builder = ReplyKeyboardBuilder()
    for module in tenant.enabled_modules:
        item = MENU_ITEMS.get(module)
        if item:
            builder.add(KeyboardButton(text=item[0]))
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
        MENU_ITEMS[m] for m in tenant.enabled_modules if m in MENU_ITEMS
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
