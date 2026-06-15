"""Помощники для оплаты: фиат (Telegram Payments) и Telegram Stars (XTR)."""

from __future__ import annotations

import math

from aiogram.types import LabeledPrice

# Способы оплаты, поддерживаемые магазином
PAY_FIAT = "fiat"  # карта через платёжного провайдера (рубли и т.п.)
PAY_STARS = "stars"  # Telegram Stars (⭐), выводятся владельцем в TON

# Курс по умолчанию: сколько рублей в одной звезде (для авто-конвертации цен)
DEFAULT_STARS_RATE_RUB = 2.0


def format_price(amount: int, currency: str = "RUB") -> str:
    """Отформатировать сумму в читаемый вид.

    Для XTR ``amount`` — целое число звёзд. Для остальных валют — минорные
    единицы (копейки/центы).
    """
    if currency == "XTR":
        return f"⭐ {amount}"
    symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸", "UAH": "₴"}
    value = amount / 100
    text = f"{value:,.0f}".replace(",", " ") if value == int(value) else f"{value:,.2f}"
    return f"{text} {symbols.get(currency, currency)}"


def to_stars(price_minor: int, rate_rub_per_star: float = DEFAULT_STARS_RATE_RUB) -> int:
    """Сконвертировать цену из копеек в звёзды по курсу (минимум 1 звезда)."""
    if rate_rub_per_star <= 0:
        rate_rub_per_star = DEFAULT_STARS_RATE_RUB
    rub = price_minor / 100
    return max(1, math.ceil(rub / rate_rub_per_star))


def product_amount(
    *,
    price_minor: int,
    price_xtr: int | None,
    mode: str,
    stars_rate: float = DEFAULT_STARS_RATE_RUB,
) -> tuple[int, str]:
    """Вернуть (сумма, валюта) для отображения и инвойса под выбранный способ.

    В режиме звёзд берётся явная ``price_xtr``, иначе цена конвертируется из ``price``.
    """
    if mode == PAY_STARS:
        stars = price_xtr if price_xtr is not None else to_stars(price_minor, stars_rate)
        return stars, "XTR"
    return price_minor, "RUB"


def labeled_prices(items: list[tuple[str, int, int]]) -> list[LabeledPrice]:
    """items: список (название, цена_за_шт, количество) -> LabeledPrice."""
    return [
        LabeledPrice(label=f"{title} ×{qty}", amount=price * qty)
        for title, price, qty in items
    ]
