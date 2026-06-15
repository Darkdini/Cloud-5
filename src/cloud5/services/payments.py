"""Помощники для оплаты через Telegram Payments."""

from __future__ import annotations

from aiogram.types import LabeledPrice


def format_price(amount: int, currency: str = "RUB") -> str:
    """Отформатировать сумму из минорных единиц (копеек) в читаемый вид."""
    symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸", "UAH": "₴"}
    value = amount / 100
    text = f"{value:,.0f}".replace(",", " ") if value == int(value) else f"{value:,.2f}"
    return f"{text} {symbols.get(currency, currency)}"


def labeled_prices(items: list[tuple[str, int, int]]) -> list[LabeledPrice]:
    """items: список (название, цена_за_шт, количество) -> LabeledPrice."""
    return [
        LabeledPrice(label=f"{title} ×{qty}", amount=price * qty)
        for title, price, qty in items
    ]
