"""Модуль записи на услуги: выбор услуги, дня и свободного слота."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloud5.core.filters import ModuleEnabled
from cloud5.core.menu import back_to_menu_button
from cloud5.core.registry import TenantInfo
from cloud5.db.models import Booking, BookingStatus, BotUser, Service
from cloud5.services.payments import format_price

router = Router(name="booking")
router.callback_query.filter(ModuleEnabled("booking"))

DAYS_AHEAD = 7
RU_MONTHS = [
    "", "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
]
RU_WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


@router.callback_query(F.data == "booking:services")
async def services(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    rows = (
        await session.execute(
            select(Service)
            .where(Service.tenant_id == tenant.id, Service.is_active.is_(True))
            .order_by(Service.id)
        )
    ).scalars().all()

    builder = InlineKeyboardBuilder()
    for s in rows:
        label = s.title
        if s.price:
            label += f" — {format_price(s.price)}"
        builder.button(text=label, callback_data=f"booking:svc:{s.id}")
    builder.add(back_to_menu_button())
    builder.adjust(1)
    text = "📅 Выберите услугу:" if rows else "Услуги пока не добавлены."
    await _edit(query, text, builder)


@router.callback_query(F.data.startswith("booking:svc:"))
async def choose_day(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    svc_id = int(query.data.split(":")[2])
    service = await session.get(Service, svc_id)
    if service is None or service.tenant_id != tenant.id:
        await query.answer("Услуга не найдена", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    today = datetime.now(UTC).date()
    for i in range(DAYS_AHEAD):
        d = today + timedelta(days=i)
        label = f"{RU_WEEKDAYS[d.weekday()]}, {d.day} {RU_MONTHS[d.month]}"
        builder.button(text=label, callback_data=f"booking:day:{svc_id}:{d.isoformat()}")
    builder.button(text="⬅️ К услугам", callback_data="booking:services")
    builder.adjust(1)
    await _edit(query, f"📅 «{service.title}» — выберите день:", builder)


@router.callback_query(F.data.startswith("booking:day:"))
async def choose_slot(
    query: CallbackQuery, tenant: TenantInfo, session: AsyncSession
) -> None:
    _, _, svc_id_s, day_s = query.data.split(":")
    svc_id = int(svc_id_s)
    day = date.fromisoformat(day_s)
    service = await session.get(Service, svc_id)
    if service is None or service.tenant_id != tenant.id:
        await query.answer("Услуга не найдена", show_alert=True)
        return

    taken = await _taken_slots(session, tenant.id, day)
    slots = _generate_slots(tenant, day, service.duration_min, taken)

    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(
            text=slot.strftime("%H:%M"),
            callback_data=f"booking:slot:{svc_id}:{slot.isoformat()}",
        )
    builder.adjust(3)
    builder.row()
    builder.button(text="⬅️ К дням", callback_data=f"booking:svc:{svc_id}")

    text = (
        "🕑 Выберите свободное время:"
        if slots
        else "На этот день свободных слотов нет 😔 Выберите другой день."
    )
    await _edit(query, text, builder)


@router.callback_query(F.data.startswith("booking:slot:"))
async def confirm_slot(
    query: CallbackQuery,
    tenant: TenantInfo,
    user: BotUser,
    session: AsyncSession,
) -> None:
    _, _, svc_id_s, iso = query.data.split(":", 3)
    svc_id = int(svc_id_s)
    starts_at = datetime.fromisoformat(iso)
    service = await session.get(Service, svc_id)
    if service is None or service.tenant_id != tenant.id:
        await query.answer("Услуга не найдена", show_alert=True)
        return

    # защита от гонки: проверяем, что слот всё ещё свободен
    taken = await _taken_slots(session, tenant.id, starts_at.date())
    if starts_at.replace(tzinfo=None) in taken:
        await query.answer("Упс, слот только что заняли. Выберите другой.", show_alert=True)
        return

    session.add(
        Booking(
            tenant_id=tenant.id,
            user_id=user.id,
            service_id=svc_id,
            starts_at=starts_at,
            status=BookingStatus.confirmed,
        )
    )
    await session.flush()

    builder = InlineKeyboardBuilder()
    builder.add(back_to_menu_button())
    await _edit(
        query,
        f"✅ Вы записаны!\n\n"
        f"Услуга: <b>{service.title}</b>\n"
        f"Когда: <b>{starts_at.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
        "Напоминание придёт заранее. До встречи!",
        builder,
    )


# --------------------------------------------------------------------------- #
# Слоты
# --------------------------------------------------------------------------- #


def _generate_slots(
    tenant: TenantInfo, day: date, duration_min: int, taken: set[datetime]
) -> list[datetime]:
    cfg = tenant.module_settings("booking")
    work_start = int(cfg.get("work_start", 10))
    work_end = int(cfg.get("work_end", 20))
    step = max(duration_min, 15)

    slots: list[datetime] = []
    cursor = datetime.combine(day, time(hour=work_start))
    end = datetime.combine(day, time(hour=work_end))
    now = datetime.now(UTC).replace(tzinfo=None)
    while cursor + timedelta(minutes=duration_min) <= end:
        if cursor > now and cursor not in taken:
            slots.append(cursor)
        cursor += timedelta(minutes=step)
    return slots


async def _taken_slots(
    session: AsyncSession, tenant_id: int, day: date
) -> set[datetime]:
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)
    rows = (
        await session.execute(
            select(Booking.starts_at).where(
                Booking.tenant_id == tenant_id,
                Booking.status != BookingStatus.cancelled,
                Booking.starts_at >= start.replace(tzinfo=UTC),
                Booking.starts_at <= end.replace(tzinfo=UTC),
            )
        )
    ).scalars().all()
    return {r.replace(tzinfo=None) for r in rows}


async def _edit(query: CallbackQuery, text: str, builder) -> None:
    if isinstance(query.message, Message):
        try:
            await query.message.edit_text(text, reply_markup=builder.as_markup())
        except Exception:  # noqa: BLE001
            await query.message.answer(text, reply_markup=builder.as_markup())
    await query.answer()
