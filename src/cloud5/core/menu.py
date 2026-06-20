"""Сборка главного меню бота по списку включённых модулей."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from cloud5.core.registry import TenantInfo

# module -> (надпись кнопки, callback_data)
MENU_ITEMS: dict[str, tuple[str, str]] = {
    "ai_assistant": ("🧠 Задать вопрос", "ai:start"),
    "shop": ("🛒 Магазин", "shop:catalog"),
    "booking": ("📅 Записаться", "booking:services"),
    "support": ("🎫 Поддержка", "support:new"),
    "donate": ("⭐ Поддержать", "donate:start"),
}


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
