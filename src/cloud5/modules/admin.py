"""Админ-панель внутри бота — конструктор магазина для владельца.

Доступна только админам тенанта (telegram_id в settings.admin.ids).
Позволяет прямо в Telegram: добавлять/удалять товары и категории, менять цены,
настраивать способы оплаты, приветствие и видеть статистику.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cloud5.core.filters import IsAdmin
from cloud5.core.menu import center_label
from cloud5.core.registry import TenantInfo
from cloud5.core.tenant_settings import patch_module_settings
from cloud5.db.models import (
    BotUser,
    Category,
    Order,
    OrderStatus,
    Product,
)
from cloud5.services.payments import (
    PAY_FIAT,
    PAY_STARS,
    format_price,
)

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class AddProduct(StatesGroup):
    title = State()
    price = State()


class EditPrice(StatesGroup):
    value = State()


class AddCategory(StatesGroup):
    title = State()


class SetRate(StatesGroup):
    value = State()


class SetProvider(StatesGroup):
    token = State()


class SetGreeting(StatesGroup):
    text = State()


# --------------------------------------------------------------------------- #
# Главное меню
# --------------------------------------------------------------------------- #


def _home_kb() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    labels = [
        ("🛒 Товары", "adm:products"),
        ("🗂 Категории", "adm:cats"),
        ("💳 Оплата", "adm:pay"),
        ("✍️ Приветствие", "adm:greeting"),
        ("📊 Статистика", "adm:stats"),
    ]
    width = max(len(t) for t, _ in labels)
    for text, data in labels:
        b.button(text=center_label(text, width), callback_data=data)
    b.adjust(1)
    return b


@router.message(Command("admin"))
async def admin_home_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=_home_kb().as_markup())


@router.callback_query(F.data == "adm:home")
async def admin_home_cb(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _edit(query, "⚙️ <b>Админ-панель</b>", _home_kb())


# --------------------------------------------------------------------------- #
# Товары
# --------------------------------------------------------------------------- #


@router.callback_query(F.data == "adm:products")
async def products_list(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    products = (
        await session.execute(
            select(Product).where(Product.tenant_id == tenant.id).order_by(Product.id)
        )
    ).scalars().all()

    b = InlineKeyboardBuilder()
    for p in products:
        b.button(
            text=f"{p.title} · {format_price(p.price, p.currency)}",
            callback_data=f"adm:prod:{p.id}",
        )
    b.button(text="➕ Добавить товар", callback_data="adm:prod:add")
    b.button(text="⬅️ Назад", callback_data="adm:home")
    b.adjust(1)
    text = "🛒 <b>Товары</b>" if products else "🛒 Товаров пока нет."
    await _edit(query, text, b)


@router.callback_query(F.data.regexp(r"^adm:prod:\d+$"))
async def product_card(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    prod_id = int(query.data.split(":")[2])
    product = await session.get(Product, prod_id)
    if product is None or product.tenant_id != tenant.id:
        await query.answer("Товар не найден", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    b.button(text="💵 Изменить цену", callback_data=f"adm:prod:price:{prod_id}")
    b.button(text="🗑 Удалить", callback_data=f"adm:prod:del:{prod_id}")
    b.button(text="⬅️ К товарам", callback_data="adm:products")
    b.adjust(1)
    text = (
        f"<b>{product.title}</b>\n"
        f"Цена: {format_price(product.price, product.currency)}"
    )
    await _edit(query, text, b)


@router.callback_query(F.data.startswith("adm:prod:del:"))
async def product_delete(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    prod_id = int(query.data.split(":")[3])
    product = await session.get(Product, prod_id)
    if product and product.tenant_id == tenant.id:
        await session.delete(product)
        await session.flush()
        await query.answer("Товар удалён 🗑")
    await products_list(query, tenant, session)


@router.callback_query(F.data == "adm:prod:add")
async def product_add_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddProduct.title)
    await _edit(query, "Введите <b>название</b> товара:", _cancel_kb())


@router.message(AddProduct.title, F.text)
async def product_add_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AddProduct.price)
    await message.answer("Введите <b>цену</b> в рублях (например 180 или 180.50):")


@router.message(AddProduct.price, F.text)
async def product_add_price(
    message: Message, tenant: TenantInfo, session: AsyncSession, state: FSMContext
) -> None:
    minor = _parse_money(message.text)
    if minor is None:
        await message.answer("Не понял цену. Введите число, например 180:")
        return
    data = await state.get_data()
    await state.clear()
    session.add(
        Product(
            tenant_id=tenant.id,
            title=data["title"],
            price=minor,
            currency="RUB",
        )
    )
    await session.flush()
    await message.answer(
        f"✅ Товар «{data['title']}» добавлен за {format_price(minor)}.",
        reply_markup=_back_kb("adm:products").as_markup(),
    )


@router.callback_query(F.data.startswith("adm:prod:price:"))
async def product_price_start(
    query: CallbackQuery, state: FSMContext
) -> None:
    prod_id = int(query.data.split(":")[3])
    await state.set_state(EditPrice.value)
    await state.update_data(prod_id=prod_id)
    await _edit(query, "Введите новую <b>цену</b> в рублях:", _cancel_kb())


@router.message(EditPrice.value, F.text)
async def product_price_save(
    message: Message, tenant: TenantInfo, session: AsyncSession, state: FSMContext
) -> None:
    minor = _parse_money(message.text)
    if minor is None:
        await message.answer("Не понял цену. Введите число, например 180:")
        return
    data = await state.get_data()
    await state.clear()
    product = await session.get(Product, data["prod_id"])
    if product and product.tenant_id == tenant.id:
        product.price = minor
        await session.flush()
        await message.answer(
            f"✅ Цена обновлена: {format_price(minor)}.",
            reply_markup=_back_kb("adm:products").as_markup(),
        )


# --------------------------------------------------------------------------- #
# Категории
# --------------------------------------------------------------------------- #


@router.callback_query(F.data == "adm:cats")
async def cats_list(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    cats = (
        await session.execute(
            select(Category).where(Category.tenant_id == tenant.id).order_by(Category.id)
        )
    ).scalars().all()
    b = InlineKeyboardBuilder()
    for c in cats:
        b.button(text=f"🗑 {c.title}", callback_data=f"adm:cat:del:{c.id}")
    b.button(text="➕ Добавить категорию", callback_data="adm:cat:add")
    b.button(text="⬅️ Назад", callback_data="adm:home")
    b.adjust(1)
    text = "🗂 <b>Категории</b> (нажмите, чтобы удалить):" if cats else "🗂 Категорий нет."
    await _edit(query, text, b)


@router.callback_query(F.data == "adm:cat:add")
async def cat_add_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddCategory.title)
    await _edit(query, "Введите название категории:", _cancel_kb())


@router.message(AddCategory.title, F.text)
async def cat_add_save(
    message: Message, tenant: TenantInfo, session: AsyncSession, state: FSMContext
) -> None:
    await state.clear()
    session.add(Category(tenant_id=tenant.id, title=message.text.strip()))
    await session.flush()
    await message.answer(
        f"✅ Категория «{message.text.strip()}» добавлена.",
        reply_markup=_back_kb("adm:cats").as_markup(),
    )


@router.callback_query(F.data.startswith("adm:cat:del:"))
async def cat_delete(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    cat_id = int(query.data.split(":")[3])
    cat = await session.get(Category, cat_id)
    if cat and cat.tenant_id == tenant.id:
        await session.delete(cat)
        await session.flush()
        await query.answer("Категория удалена 🗑")
    await cats_list(query, tenant, session)


# --------------------------------------------------------------------------- #
# Оплата
# --------------------------------------------------------------------------- #


def _methods(tenant: TenantInfo) -> list[str]:
    cfg = tenant.module_settings("shop")
    methods = cfg.get("methods")
    if methods:
        return [m for m in methods if m in (PAY_STARS, PAY_FIAT)]
    return [cfg.get("payment", PAY_FIAT)]


@router.callback_query(F.data == "adm:pay")
async def pay_menu(query: CallbackQuery, tenant: TenantInfo) -> None:
    methods = _methods(tenant)
    cfg = tenant.module_settings("shop")
    stars_on = "✅" if PAY_STARS in methods else "❌"
    fiat_on = "✅" if PAY_FIAT in methods else "❌"
    rate = cfg.get("stars_rate", 2.0)
    has_provider = "задан" if cfg.get("provider_token") else "не задан"

    b = InlineKeyboardBuilder()
    b.button(text=f"{stars_on} ⭐ Звёзды", callback_data="adm:pay:toggle:stars")
    b.button(text=f"{fiat_on} 💳 Карта", callback_data="adm:pay:toggle:fiat")
    b.button(text=f"💱 Курс звезды: {rate} ₽", callback_data="adm:pay:rate")
    b.button(text="🔑 Токен провайдера", callback_data="adm:pay:provider")
    b.button(text="⬅️ Назад", callback_data="adm:home")
    b.adjust(2, 1, 1, 1)
    await _edit(
        query,
        "💳 <b>Способы оплаты</b>\n"
        f"⭐ Звёзды (вывод в TON): {stars_on}\n"
        f"💳 Карта: {fiat_on} (токен провайдера {has_provider})",
        b,
    )


@router.callback_query(F.data.startswith("adm:pay:toggle:"))
async def pay_toggle(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    which = PAY_STARS if query.data.endswith(":stars") else PAY_FIAT
    methods = set(_methods(tenant))
    if which in methods:
        methods.discard(which)
    else:
        methods.add(which)
    if not methods:
        await query.answer("Должен остаться хотя бы один способ", show_alert=True)
        return
    ordered = [m for m in (PAY_STARS, PAY_FIAT) if m in methods]
    await patch_module_settings(session, tenant, "shop", {"methods": ordered})
    await pay_menu(query, tenant)


@router.callback_query(F.data == "adm:pay:rate")
async def pay_rate_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetRate.value)
    await _edit(query, "Введите курс — сколько рублей в одной звезде (напр. 2):", _cancel_kb())


@router.message(SetRate.value, F.text)
async def pay_rate_save(
    message: Message, tenant: TenantInfo, session: AsyncSession, state: FSMContext
) -> None:
    try:
        rate = float(message.text.replace(",", "."))
        assert rate > 0
    except (ValueError, AssertionError):
        await message.answer("Введите положительное число, например 2:")
        return
    await state.clear()
    await patch_module_settings(session, tenant, "shop", {"stars_rate": rate})
    await message.answer(
        f"✅ Курс звезды: {rate} ₽.",
        reply_markup=_back_kb("adm:pay").as_markup(),
    )


@router.callback_query(F.data == "adm:pay:provider")
async def pay_provider_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetProvider.token)
    await _edit(
        query,
        "Пришлите токен платёжного провайдера (из @BotFather → Payments).\n"
        "Отправьте «-» чтобы очистить.",
        _cancel_kb(),
    )


@router.message(SetProvider.token, F.text)
async def pay_provider_save(
    message: Message, tenant: TenantInfo, session: AsyncSession, state: FSMContext
) -> None:
    await state.clear()
    token = message.text.strip()
    value = "" if token == "-" else token
    await patch_module_settings(session, tenant, "shop", {"provider_token": value})
    await message.answer(
        "✅ Токен сохранён." if value else "✅ Токен очищен.",
        reply_markup=_back_kb("adm:pay").as_markup(),
    )


# --------------------------------------------------------------------------- #
# Приветствие
# --------------------------------------------------------------------------- #


@router.callback_query(F.data == "adm:greeting")
async def greeting_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetGreeting.text)
    await _edit(
        query,
        "Пришлите новый текст приветствия (показывается на /start):",
        _cancel_kb(),
    )


@router.message(SetGreeting.text, F.text)
async def greeting_save(
    message: Message, tenant: TenantInfo, session: AsyncSession, state: FSMContext
) -> None:
    await state.clear()
    await patch_module_settings(
        session, tenant, "common", {"greeting": message.text.strip()}
    )
    await message.answer(
        "✅ Приветствие обновлено.",
        reply_markup=_back_kb("adm:home").as_markup(),
    )


# --------------------------------------------------------------------------- #
# Статистика
# --------------------------------------------------------------------------- #


@router.callback_query(F.data == "adm:stats")
async def stats(query: CallbackQuery, tenant: TenantInfo, session: AsyncSession) -> None:
    users = await session.scalar(
        select(func.count()).select_from(BotUser).where(BotUser.tenant_id == tenant.id)
    )
    orders = await session.scalar(
        select(func.count()).select_from(Order).where(Order.tenant_id == tenant.id)
    )
    revenue = await session.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.tenant_id == tenant.id,
            Order.status.in_([OrderStatus.paid, OrderStatus.completed]),
        )
    )
    await _edit(
        query,
        "📊 <b>Статистика</b>\n"
        f"👥 Пользователей: {users or 0}\n"
        f"📦 Заказов: {orders or 0}\n"
        f"💰 Выручка (оплачено): {revenue or 0}",
        _back_kb("adm:home"),
    )


# --------------------------------------------------------------------------- #
# Помощники
# --------------------------------------------------------------------------- #


def _cancel_kb() -> InlineKeyboardBuilder:
    return _back_kb("adm:home", text="✖️ Отмена")


def _back_kb(target: str, text: str = "⬅️ Назад") -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.button(text=text, callback_data=target)
    return b


def _parse_money(text: str | None) -> int | None:
    """Рубли '180' / '180.50' → минорные единицы (копейки). None при ошибке."""
    if not text:
        return None
    try:
        value = float(text.strip().replace(",", ".").replace(" ", ""))
    except ValueError:
        return None
    if value < 0:
        return None
    return round(value * 100)


async def _edit(query: CallbackQuery, text: str, builder: InlineKeyboardBuilder) -> None:
    if isinstance(query.message, Message):
        try:
            await query.message.edit_text(text, reply_markup=builder.as_markup())
        except Exception:  # noqa: BLE001
            await query.message.answer(text, reply_markup=builder.as_markup())
    await query.answer()
