"""Модуль магазина: каталог, корзина, оформление и оплата заказа."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    Message,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cloud5.core.filters import ModuleEnabled
from cloud5.core.logging import get_logger
from cloud5.core.menu import back_to_menu_button, respond
from cloud5.core.registry import TenantInfo
from cloud5.db.models import (
    BotUser,
    CartItem,
    Category,
    Order,
    OrderItem,
    OrderStatus,
    Product,
)
from cloud5.services.payments import (
    DEFAULT_STARS_RATE_RUB,
    PAY_FIAT,
    PAY_STARS,
    format_price,
    labeled_prices,
    product_amount,
)

log = get_logger("shop")

router = Router(name="shop")
router.callback_query.filter(ModuleEnabled("shop"))
router.message.filter(ModuleEnabled("shop"))


# --------------------------------------------------------------------------- #
# Способ оплаты (per-tenant)
# --------------------------------------------------------------------------- #


def _available_methods(tenant: TenantInfo) -> list[str]:
    """Доступные способы оплаты у тенанта.

    Приоритет — список ``settings.shop.methods`` (напр. ["stars", "fiat"]).
    Для обратной совместимости — одиночное поле ``settings.shop.payment``.
    """
    cfg = tenant.module_settings("shop")
    methods = cfg.get("methods")
    if methods:
        filtered = [m for m in methods if m in (PAY_STARS, PAY_FIAT)]
        if filtered:
            return filtered
    return [cfg.get("payment", PAY_FIAT)]


def _pay_mode(tenant: TenantInfo) -> str:
    """Способ оплаты для отображения цен (первый из доступных)."""
    return _available_methods(tenant)[0]


def _stars_rate(tenant: TenantInfo) -> float:
    return float(
        tenant.module_settings("shop").get("stars_rate", DEFAULT_STARS_RATE_RUB)
    )


def _price_view(tenant: TenantInfo, product: Product) -> str:
    """Отформатированная цена товара под выбранный способ оплаты."""
    amount, currency = product_amount(
        price_minor=product.price,
        price_xtr=product.price_xtr,
        mode=_pay_mode(tenant),
        stars_rate=_stars_rate(tenant),
    )
    return format_price(amount, currency)


# --------------------------------------------------------------------------- #
# Каталог
# --------------------------------------------------------------------------- #


@router.callback_query(F.data == "shop:catalog")
async def catalog(
    query: CallbackQuery | Message, tenant: TenantInfo, session: AsyncSession
) -> None:
    categories = (
        await session.execute(
            select(Category)
            .where(Category.tenant_id == tenant.id, Category.is_active.is_(True))
            .order_by(Category.sort_order, Category.id)
        )
    ).scalars().all()

    builder = InlineKeyboardBuilder()
    if categories:
        text = "🛒 Выберите категорию:"
        for cat in categories:
            builder.button(text=cat.title, callback_data=f"shop:cat:{cat.id}")
    else:
        text = "🛒 Каталог:"
        products = await _active_products(session, tenant.id, category_id=None)
        for p in products:
            builder.button(
                text=f"{p.title} — {_price_view(tenant, p)}",
                callback_data=f"shop:prod:{p.id}",
            )
        if not products:
            text = "Каталог пока пуст. Загляните позже!"

    builder.button(text="🧺 Корзина", callback_data="shop:cart")
    builder.add(back_to_menu_button())
    builder.adjust(1)
    await respond(query, text, builder.as_markup())


@router.callback_query(F.data.startswith("shop:cat:"))
async def category_products(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    cat_id = int(query.data.split(":")[2])
    products = await _active_products(session, tenant.id, category_id=cat_id)

    builder = InlineKeyboardBuilder()
    for p in products:
        builder.button(
            text=f"{p.title} — {_price_view(tenant, p)}",
            callback_data=f"shop:prod:{p.id}",
        )
    builder.button(text="⬅️ К категориям", callback_data="shop:catalog")
    builder.adjust(1)
    text = "Товары:" if products else "В этой категории пока пусто."
    await _edit(query, text, builder)


@router.callback_query(F.data.startswith("shop:prod:"))
async def product_card(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    prod_id = int(query.data.split(":")[2])
    product = await session.get(Product, prod_id)
    if product is None or product.tenant_id != tenant.id:
        await query.answer("Товар не найден", show_alert=True)
        return

    text = f"<b>{product.title}</b>\n\n"
    if product.description:
        text += f"{product.description}\n\n"
    text += f"Цена: {_price_view(tenant, product)}"

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ В корзину", callback_data=f"shop:add:{product.id}")
    builder.button(text="🧺 Корзина", callback_data="shop:cart")
    builder.button(text="⬅️ Назад", callback_data="shop:catalog")
    builder.adjust(1)
    await _edit(query, text, builder)


# --------------------------------------------------------------------------- #
# Корзина
# --------------------------------------------------------------------------- #


@router.callback_query(F.data.startswith("shop:add:"))
async def add_to_cart(
    query: CallbackQuery, tenant: TenantInfo, user: BotUser, session: AsyncSession
) -> None:
    prod_id = int(query.data.split(":")[2])
    product = await session.get(Product, prod_id)
    if product is None or product.tenant_id != tenant.id or not product.is_active:
        await query.answer("Товар недоступен", show_alert=True)
        return

    item = (
        await session.execute(
            select(CartItem).where(
                CartItem.user_id == user.id, CartItem.product_id == prod_id
            )
        )
    ).scalar_one_or_none()
    if item is None:
        session.add(
            CartItem(
                tenant_id=tenant.id,
                user_id=user.id,
                product_id=prod_id,
                quantity=1,
            )
        )
    else:
        item.quantity += 1
    await session.flush()
    await query.answer("Добавлено в корзину ✅")


@router.callback_query(F.data == "shop:cart")
async def show_cart(
    query: CallbackQuery,
    tenant: TenantInfo,
    user: BotUser,
    session: AsyncSession,
) -> None:
    items = await _cart_items(session, user.id)
    if not items:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ В каталог", callback_data="shop:catalog")
        await _edit(query, "🧺 Корзина пуста.", builder)
        return

    mode = _pay_mode(tenant)
    rate = _stars_rate(tenant)
    lines = ["🧺 <b>Ваша корзина:</b>\n"]
    total = 0
    currency = "RUB"
    builder = InlineKeyboardBuilder()
    for item in items:
        p = item.product
        unit, currency = product_amount(
            price_minor=p.price, price_xtr=p.price_xtr, mode=mode, stars_rate=rate
        )
        line_total = unit * item.quantity
        total += line_total
        lines.append(
            f"• {p.title} — {item.quantity} × "
            f"{format_price(unit, currency)} = "
            f"{format_price(line_total, currency)}"
        )
        builder.button(text=f"➖ {p.title}", callback_data=f"shop:dec:{p.id}")
        builder.button(text=f"➕ {p.title}", callback_data=f"shop:inc:{p.id}")
    lines.append(f"\n<b>Итого: {format_price(total, currency)}</b>")

    builder.button(text="✅ Оформить заказ", callback_data="shop:checkout")
    builder.button(text="🗑 Очистить", callback_data="shop:clear")
    builder.button(text="⬅️ В каталог", callback_data="shop:catalog")
    builder.adjust(2)
    await _edit(query, "\n".join(lines), builder)


@router.callback_query(F.data.startswith("shop:inc:"))
async def cart_inc(
    query: CallbackQuery, tenant: TenantInfo, user: BotUser, session: AsyncSession
) -> None:
    await _change_qty(query, tenant, user, session, delta=1)


@router.callback_query(F.data.startswith("shop:dec:"))
async def cart_dec(
    query: CallbackQuery, tenant: TenantInfo, user: BotUser, session: AsyncSession
) -> None:
    await _change_qty(query, tenant, user, session, delta=-1)


@router.callback_query(F.data == "shop:clear")
async def cart_clear(
    query: CallbackQuery, tenant: TenantInfo, user: BotUser, session: AsyncSession
) -> None:
    for item in await _cart_items(session, user.id):
        await session.delete(item)
    await session.flush()
    await show_cart(query, tenant, user, session)


# --------------------------------------------------------------------------- #
# Оформление и оплата
# --------------------------------------------------------------------------- #


@router.callback_query(F.data == "shop:checkout")
async def checkout(
    query: CallbackQuery,
    tenant: TenantInfo,
    user: BotUser,
    session: AsyncSession,
) -> None:
    items = await _cart_items(session, user.id)
    if not items:
        await query.answer("Корзина пуста", show_alert=True)
        return

    methods = _available_methods(tenant)
    if len(methods) > 1:
        # клиент сам выбирает способ оплаты
        builder = InlineKeyboardBuilder()
        if PAY_STARS in methods:
            builder.button(text="⭐ Оплатить звёздами", callback_data="shop:pay:stars")
        if PAY_FIAT in methods:
            builder.button(text="💳 Оплатить картой", callback_data="shop:pay:fiat")
        builder.button(text="⬅️ В корзину", callback_data="shop:cart")
        builder.adjust(1)
        await _edit(query, "Выберите способ оплаты:", builder)
        return

    await _create_order_and_invoice(query, tenant, user, session, methods[0])


@router.callback_query(F.data.startswith("shop:pay:"))
async def choose_payment(
    query: CallbackQuery,
    tenant: TenantInfo,
    user: BotUser,
    session: AsyncSession,
) -> None:
    mode = PAY_STARS if query.data.endswith(":stars") else PAY_FIAT
    if mode not in _available_methods(tenant):
        await query.answer("Способ оплаты недоступен", show_alert=True)
        return
    await _create_order_and_invoice(query, tenant, user, session, mode)


async def _create_order_and_invoice(
    query: CallbackQuery,
    tenant: TenantInfo,
    user: BotUser,
    session: AsyncSession,
    mode: str,
) -> None:
    items = await _cart_items(session, user.id)
    if not items:
        await query.answer("Корзина пуста", show_alert=True)
        return

    rate = _stars_rate(tenant)

    # считаем цену каждой позиции в выбранной валюте (рубли или звёзды)
    priced = []  # (product, unit_amount, qty)
    currency = "RUB"
    for i in items:
        unit, currency = product_amount(
            price_minor=i.product.price,
            price_xtr=i.product.price_xtr,
            mode=mode,
            stars_rate=rate,
        )
        priced.append((i.product, unit, i.quantity))
    total = sum(unit * qty for _, unit, qty in priced)

    order = Order(
        tenant_id=tenant.id,
        user_id=user.id,
        status=OrderStatus.new,
        total=total,
        currency=currency,
        items=[
            OrderItem(
                product_id=p.id,
                title=p.title,
                price=unit,
                quantity=qty,
            )
            for p, unit, qty in priced
        ],
    )
    session.add(order)
    # корзину очищаем
    for i in items:
        await session.delete(i)
    await session.flush()

    description = ", ".join(f"{p.title} ×{qty}" for p, _, qty in priced)[:255]
    invoice_prices = labeled_prices([(p.title, unit, qty) for p, unit, qty in priced])

    if mode == PAY_STARS and isinstance(query.message, Message):
        # Telegram Stars: provider_token пустой, валюта XTR. Выводятся в TON.
        await query.message.answer_invoice(
            title=f"Заказ #{order.id}",
            description=description,
            payload=f"order:{order.id}",
            provider_token="",
            currency="XTR",
            prices=invoice_prices,
        )
        await query.answer()
        return

    provider_token = tenant.module_settings("shop").get("provider_token")
    if mode == PAY_FIAT and provider_token and isinstance(query.message, Message):
        await query.message.answer_invoice(
            title=f"Заказ #{order.id}",
            description=description,
            payload=f"order:{order.id}",
            provider_token=provider_token,
            currency=currency,
            prices=invoice_prices,
        )
        await query.answer()
    else:
        # Без платёжного провайдера — заказ принят, свяжется менеджер
        builder = InlineKeyboardBuilder()
        builder.add(back_to_menu_button())
        await _edit(
            query,
            f"✅ Заказ #{order.id} на сумму "
            f"{format_price(total, currency)} принят!\n"
            "Менеджер свяжется с вами для подтверждения.",
            builder,
        )


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment.func(lambda p: p.invoice_payload.startswith("order:")))
async def on_paid(
    message: Message, tenant: TenantInfo, session: AsyncSession
) -> None:
    payload = message.successful_payment.invoice_payload
    if payload.startswith("order:"):
        order_id = int(payload.split(":")[1])
        order = await session.get(Order, order_id)
        if order and order.tenant_id == tenant.id:
            sp = message.successful_payment
            order.status = OrderStatus.paid
            # для Stars provider_* пустой — берём telegram_payment_charge_id
            order.payment_id = (
                sp.provider_payment_charge_id or sp.telegram_payment_charge_id
            )
            await session.flush()
    await message.answer(
        "🎉 Оплата прошла успешно! Спасибо за заказ.\n"
        "Мы уже приступили к его обработке."
    )


# --------------------------------------------------------------------------- #
# Внутренние помощники
# --------------------------------------------------------------------------- #


async def _active_products(
    session: AsyncSession, tenant_id: int, category_id: int | None
) -> list[Product]:
    stmt = select(Product).where(
        Product.tenant_id == tenant_id, Product.is_active.is_(True)
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    stmt = stmt.order_by(Product.id)
    return list((await session.execute(stmt)).scalars().all())


async def _cart_items(session: AsyncSession, user_id: int) -> list[CartItem]:
    rows = (
        await session.execute(
            select(CartItem)
            .where(CartItem.user_id == user_id)
            .options(selectinload(CartItem.product))
            .order_by(CartItem.id)
        )
    ).scalars().all()
    return list(rows)


async def _change_qty(
    query: CallbackQuery,
    tenant: TenantInfo,
    user: BotUser,
    session: AsyncSession,
    delta: int,
) -> None:
    prod_id = int(query.data.split(":")[2])
    item = (
        await session.execute(
            select(CartItem).where(
                CartItem.user_id == user.id, CartItem.product_id == prod_id
            )
        )
    ).scalar_one_or_none()
    if item is not None:
        item.quantity += delta
        if item.quantity <= 0:
            await session.delete(item)
        await session.flush()
    await show_cart(query, tenant, user, session)


async def _edit(query: CallbackQuery, text: str, builder) -> None:
    markup = builder.as_markup() if hasattr(builder, "as_markup") else builder
    if isinstance(query.message, Message):
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except Exception:  # noqa: BLE001 — сообщение могло быть с медиа
            await query.message.answer(text, reply_markup=markup)
    await query.answer()
