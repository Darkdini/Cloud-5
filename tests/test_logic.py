"""Юнит-тесты бизнес-логики без внешних зависимостей."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cloud5.core.menu import main_menu
from cloud5.core.registry import TenantInfo
from cloud5.modules.booking import _generate_slots
from cloud5.services.ai import build_system_prompt
from cloud5.services.payments import (
    PAY_FIAT,
    PAY_STARS,
    format_price,
    product_amount,
    to_stars,
)


def make_tenant(**kwargs) -> TenantInfo:
    base = dict(
        id=1,
        title="Test",
        bot_token="123:ABC",
        bot_username="test_bot",
        locale="ru",
        enabled_modules=[],
        settings={},
    )
    base.update(kwargs)
    return TenantInfo(**base)


def test_format_price_rub():
    assert format_price(150000, "RUB") == "1 500 ₽"
    assert format_price(99, "RUB") == "0.99 ₽"


def test_format_price_usd():
    assert format_price(100000, "USD") == "1 000 $"


def test_format_price_stars():
    assert format_price(150, "XTR") == "⭐ 150"


def test_to_stars_rounds_up_and_min_one():
    # 300 ₽ при курсе 2 ₽/звезда = 150 звёзд
    assert to_stars(30000, 2.0) == 150
    # дробное — округляем вверх
    assert to_stars(30050, 2.0) == 151
    # очень дёшево — минимум 1 звезда
    assert to_stars(1, 2.0) == 1


def test_product_amount_fiat_vs_stars():
    # фиат: возвращает копейки и RUB
    assert product_amount(price_minor=30000, price_xtr=None, mode=PAY_FIAT) == (
        30000,
        "RUB",
    )
    # звёзды без явной цены: конвертация из рублей
    amount, cur = product_amount(
        price_minor=30000, price_xtr=None, mode=PAY_STARS, stars_rate=2.0
    )
    assert cur == "XTR" and amount == 150
    # звёзды с явной ценой: берётся price_xtr
    assert product_amount(price_minor=30000, price_xtr=99, mode=PAY_STARS) == (
        99,
        "XTR",
    )


def test_tenant_has_module():
    t = make_tenant(enabled_modules=["shop", "ai_assistant"])
    assert t.has_module("shop")
    assert not t.has_module("booking")


def test_module_settings():
    t = make_tenant(settings={"ai_assistant": {"persona": "Бот-продажник"}})
    assert t.module_settings("ai_assistant")["persona"] == "Бот-продажник"
    assert t.module_settings("unknown") == {}


def test_main_menu_only_enabled_modules():
    t = make_tenant(enabled_modules=["shop", "support"])
    markup = main_menu(t)
    datas = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "shop:catalog" in datas
    assert "support:new" in datas
    assert "ai:start" not in datas


def test_build_system_prompt_with_knowledge():
    prompt = build_system_prompt("Ты ассистент", ["Доставка 1 день"])
    assert "Ты ассистент" in prompt
    assert "Доставка 1 день" in prompt
    assert "<knowledge>" in prompt


def test_generate_slots_basic():
    t = make_tenant(settings={"booking": {"work_start": 10, "work_end": 12}})
    day = (datetime.now(UTC) + timedelta(days=3)).date()
    slots = _generate_slots(t, day, duration_min=60, taken=set())
    # 10:00 и 11:00 — два часовых слота в окне 10-12
    assert len(slots) == 2
    assert slots[0].hour == 10
    assert slots[1].hour == 11


def test_generate_slots_excludes_taken():
    t = make_tenant(settings={"booking": {"work_start": 10, "work_end": 13}})
    day = (datetime.now(UTC) + timedelta(days=3)).date()
    taken = {datetime.combine(day, datetime.min.time()).replace(hour=11)}
    slots = _generate_slots(t, day, duration_min=60, taken=taken)
    hours = {s.hour for s in slots}
    assert 11 not in hours
    assert 10 in hours and 12 in hours
