"""FastAPI админ-API: управление тенантами, контентом, рассылками и статистикой."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cloud5.admin import schemas as s
from cloud5.config import settings
from cloud5.db.models import (
    Booking,
    BotUser,
    Broadcast,
    Category,
    KnowledgeDoc,
    Order,
    OrderStatus,
    Product,
    Service,
    Tenant,
    Ticket,
    TicketStatus,
)
from cloud5.db.session import get_session, init_engine
from cloud5.services.broadcast import run_broadcast

app = FastAPI(title="Cloud-5 Admin API", version="0.1.0")


@app.on_event("startup")
async def _startup() -> None:
    init_engine()


async def require_admin(x_admin_token: str = Header(default="")) -> None:
    if x_admin_token != settings.admin_api_token:
        raise HTTPException(status_code=401, detail="invalid admin token")


async def _get_tenant(session: AsyncSession, tenant_id: int) -> Tenant:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="tenant not found")
    return tenant


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #


@app.get("/health", response_model=s.HealthOut)
async def health() -> s.HealthOut:
    return s.HealthOut(status="ok", time=datetime.now(UTC))


# --------------------------------------------------------------------------- #
# Тенанты
# --------------------------------------------------------------------------- #


@app.post("/tenants", response_model=s.TenantOut, dependencies=[Depends(require_admin)])
async def create_tenant(
    body: s.TenantCreate, session: AsyncSession = Depends(get_session)
) -> Tenant:
    tenant = Tenant(
        title=body.title,
        bot_token=body.bot_token,
        bot_username=body.bot_username,
        locale=body.locale,
        enabled_modules=body.enabled_modules,
        settings=body.settings,
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)
    return tenant


@app.get("/tenants", response_model=list[s.TenantOut], dependencies=[Depends(require_admin)])
async def list_tenants(session: AsyncSession = Depends(get_session)) -> list[Tenant]:
    rows = (await session.execute(select(Tenant).order_by(Tenant.id))).scalars().all()
    return list(rows)


@app.patch(
    "/tenants/{tenant_id}",
    response_model=s.TenantOut,
    dependencies=[Depends(require_admin)],
)
async def update_tenant(
    tenant_id: int,
    body: s.TenantUpdate,
    session: AsyncSession = Depends(get_session),
) -> Tenant:
    tenant = await _get_tenant(session, tenant_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)
    await session.commit()
    await session.refresh(tenant)
    return tenant


# --------------------------------------------------------------------------- #
# Контент магазина
# --------------------------------------------------------------------------- #


@app.post(
    "/tenants/{tenant_id}/categories",
    response_model=s.IdOut,
    dependencies=[Depends(require_admin)],
)
async def add_category(
    tenant_id: int,
    body: s.CategoryCreate,
    session: AsyncSession = Depends(get_session),
) -> s.IdOut:
    await _get_tenant(session, tenant_id)
    cat = Category(tenant_id=tenant_id, title=body.title, sort_order=body.sort_order)
    session.add(cat)
    await session.commit()
    await session.refresh(cat)
    return s.IdOut(id=cat.id)


@app.post(
    "/tenants/{tenant_id}/products",
    response_model=s.IdOut,
    dependencies=[Depends(require_admin)],
)
async def add_product(
    tenant_id: int,
    body: s.ProductCreate,
    session: AsyncSession = Depends(get_session),
) -> s.IdOut:
    await _get_tenant(session, tenant_id)
    product = Product(tenant_id=tenant_id, **body.model_dump())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return s.IdOut(id=product.id)


# --------------------------------------------------------------------------- #
# Услуги (booking)
# --------------------------------------------------------------------------- #


@app.post(
    "/tenants/{tenant_id}/services",
    response_model=s.IdOut,
    dependencies=[Depends(require_admin)],
)
async def add_service(
    tenant_id: int,
    body: s.ServiceCreate,
    session: AsyncSession = Depends(get_session),
) -> s.IdOut:
    await _get_tenant(session, tenant_id)
    service = Service(tenant_id=tenant_id, **body.model_dump())
    session.add(service)
    await session.commit()
    await session.refresh(service)
    return s.IdOut(id=service.id)


# --------------------------------------------------------------------------- #
# База знаний (ai_assistant)
# --------------------------------------------------------------------------- #


@app.post(
    "/tenants/{tenant_id}/knowledge",
    response_model=s.IdOut,
    dependencies=[Depends(require_admin)],
)
async def add_knowledge(
    tenant_id: int,
    body: s.KnowledgeCreate,
    session: AsyncSession = Depends(get_session),
) -> s.IdOut:
    await _get_tenant(session, tenant_id)
    doc = KnowledgeDoc(tenant_id=tenant_id, title=body.title, content=body.content)
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return s.IdOut(id=doc.id)


# --------------------------------------------------------------------------- #
# Рассылки (CRM)
# --------------------------------------------------------------------------- #


@app.post(
    "/tenants/{tenant_id}/broadcasts",
    response_model=s.IdOut,
    dependencies=[Depends(require_admin)],
)
async def create_broadcast(
    tenant_id: int,
    body: s.BroadcastCreate,
    session: AsyncSession = Depends(get_session),
) -> s.IdOut:
    await _get_tenant(session, tenant_id)
    broadcast = Broadcast(
        tenant_id=tenant_id,
        title=body.title,
        text=body.text,
        photo_url=body.photo_url,
        segment=body.segment,
    )
    session.add(broadcast)
    await session.commit()
    await session.refresh(broadcast)
    return s.IdOut(id=broadcast.id)


@app.post(
    "/broadcasts/{broadcast_id}/send",
    response_model=s.MessageOut,
    dependencies=[Depends(require_admin)],
)
async def send_broadcast(
    broadcast_id: int, background: BackgroundTasks
) -> s.MessageOut:
    background.add_task(run_broadcast, broadcast_id)
    return s.MessageOut(detail=f"broadcast {broadcast_id} queued")


# --------------------------------------------------------------------------- #
# Статистика
# --------------------------------------------------------------------------- #


@app.get(
    "/tenants/{tenant_id}/stats",
    response_model=s.TenantStats,
    dependencies=[Depends(require_admin)],
)
async def tenant_stats(
    tenant_id: int, session: AsyncSession = Depends(get_session)
) -> s.TenantStats:
    await _get_tenant(session, tenant_id)

    users = await session.scalar(
        select(func.count()).select_from(BotUser).where(BotUser.tenant_id == tenant_id)
    )
    orders = await session.scalar(
        select(func.count()).select_from(Order).where(Order.tenant_id == tenant_id)
    )
    revenue = await session.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.tenant_id == tenant_id,
            Order.status.in_(
                [OrderStatus.paid, OrderStatus.completed, OrderStatus.shipped]
            ),
        )
    )
    bookings = await session.scalar(
        select(func.count()).select_from(Booking).where(Booking.tenant_id == tenant_id)
    )
    open_tickets = await session.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.tenant_id == tenant_id, Ticket.status == TicketStatus.open)
    )
    return s.TenantStats(
        users=users or 0,
        orders=orders or 0,
        revenue=revenue or 0,
        bookings=bookings or 0,
        open_tickets=open_tickets or 0,
    )
