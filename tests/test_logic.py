"""Юнит-тесты логики донат-бота без внешних зависимостей."""

from __future__ import annotations

from cloud5.core.menu import (
    donate_amount_for_label,
    donate_amounts,
    donate_label,
    main_reply_menu,
)
from cloud5.core.registry import TenantInfo
from cloud5.services.card import render_donor_card


def make_tenant(**kwargs) -> TenantInfo:
    base = dict(
        id=1,
        title="Test",
        bot_token="123:ABC",
        bot_username="test_bot",
        locale="ru",
        enabled_modules=["donate"],
        settings={},
    )
    base.update(kwargs)
    return TenantInfo(**base)


def test_tenant_has_module():
    t = make_tenant(enabled_modules=["donate"])
    assert t.has_module("donate")
    assert not t.has_module("shop")


def test_module_settings():
    t = make_tenant(settings={"donate": {"amounts": [50, 100]}})
    assert t.module_settings("donate")["amounts"] == [50, 100]
    assert t.module_settings("unknown") == {}


def test_donate_amounts_default():
    t = make_tenant(settings={})
    assert donate_amounts(t) == [100]


def test_donate_amounts_from_settings():
    t = make_tenant(settings={"donate": {"amounts": [100, 200, 1000]}})
    assert donate_amounts(t) == [100, 200, 1000]


def test_donate_amounts_backward_compat_single():
    t = make_tenant(settings={"donate": {"amount_xtr": 250}})
    assert donate_amounts(t) == [250]


def test_donate_label_plural():
    assert donate_label(1) == "⭐ 1 звезда"
    assert donate_label(2) == "⭐ 2 звезды"
    assert donate_label(5) == "⭐ 5 звёзд"
    assert donate_label(100) == "⭐ 100 звёзд"
    assert donate_label(1000, top=True) == "🔥 1000 звёзд (ТОП)"


def test_donate_amount_for_label_roundtrip():
    t = make_tenant(settings={"donate": {"amounts": [100, 200, 1000]}})
    assert donate_amount_for_label(t, "⭐ 100 звёзд") == 100
    assert donate_amount_for_label(t, "🔥 1000 звёзд (ТОП)") == 1000
    assert donate_amount_for_label(t, "что-то ещё") is None


def test_main_reply_menu_buttons():
    t = make_tenant(settings={"donate": {"amounts": [100, 200, 1000]}})
    buttons = [b.text for row in main_reply_menu(t).keyboard for b in row]
    assert buttons == ["⭐ 100 звёзд", "⭐ 200 звёзд", "🔥 1000 звёзд (ТОП)"]


def test_render_donor_card_returns_png_or_none():
    # При установленном Pillow — PNG-байты; без него — None (текстовый фолбэк).
    data = render_donor_card("@tester", 100)
    if data is not None:
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
