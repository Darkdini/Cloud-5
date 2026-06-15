"""Доменные модели платформы Cloud-5.

Все бизнес-сущности привязаны к тенанту (боту клиента) через ``tenant_id``,
что обеспечивает полную изоляцию данных между разными ботами на одном движке.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cloud5.db.base import Base, PKMixin, TimestampMixin
from cloud5.db.types import JSONType

# ---------------------------------------------------------------------------
# Тенант (бот клиента)
# ---------------------------------------------------------------------------


class Tenant(Base, PKMixin, TimestampMixin):
    """Один бот клиента. Хранит токен и набор включённых модулей."""

    __tablename__ = "tenants"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    bot_token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    bot_username: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)

    # Список включённых модулей, напр. ["ai_assistant", "shop"]
    enabled_modules: Mapped[list[str]] = mapped_column(
        JSONType, default=list, nullable=False
    )
    # Произвольные настройки модулей: {"ai_assistant": {...}, "shop": {...}}
    settings: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    users: Mapped[list[BotUser]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )

    def module_settings(self, module: str) -> dict:
        return (self.settings or {}).get(module, {})

    def has_module(self, module: str) -> bool:
        return module in (self.enabled_modules or [])


# ---------------------------------------------------------------------------
# Пользователь бота (клиент клиента)
# ---------------------------------------------------------------------------


class BotUser(Base, PKMixin, TimestampMixin):
    """Конечный пользователь конкретного бота."""

    __tablename__ = "bot_users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "telegram_id", name="uq_user_tenant_tg"),
        Index("ix_bot_users_tenant", "tenant_id"),
    )

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    locale: Mapped[str | None] = mapped_column(String(8))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attributes: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="users")

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p) or "—"


# ---------------------------------------------------------------------------
# AI-ассистент: память диалога
# ---------------------------------------------------------------------------


class ChatRole(enum.StrEnum):
    user = "user"
    assistant = "assistant"


class ChatMessage(Base, PKMixin, TimestampMixin):
    """Сообщение в диалоге с ИИ-ассистентом (долговременная память)."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_user", "tenant_id", "user_id", "id"),
    )

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("bot_users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int | None] = mapped_column(Integer)


class KnowledgeDoc(Base, PKMixin, TimestampMixin):
    """Документ базы знаний для ИИ-ассистента (контекст про бизнес клиента)."""

    __tablename__ = "knowledge_docs"
    __table_args__ = (Index("ix_knowledge_tenant", "tenant_id"),)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ---------------------------------------------------------------------------
# Магазин
# ---------------------------------------------------------------------------


class Category(Base, PKMixin, TimestampMixin):
    __tablename__ = "categories"
    __table_args__ = (Index("ix_categories_tenant", "tenant_id"),)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    products: Mapped[list[Product]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class Product(Base, PKMixin, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_tenant", "tenant_id"),)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Цена в минимальных единицах валюты (копейки/центы)
    price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String(1024))
    stock: Mapped[int | None] = mapped_column(Integer)  # None = безлимит
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category: Mapped[Category | None] = relationship(back_populates="products")


class CartItem(Base, PKMixin, TimestampMixin):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),
        Index("ix_cart_tenant_user", "tenant_id", "user_id"),
    )

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("bot_users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    product: Mapped[Product] = relationship()


class OrderStatus(enum.StrEnum):
    new = "new"
    paid = "paid"
    processing = "processing"
    shipped = "shipped"
    completed = "completed"
    cancelled = "cancelled"


class Order(Base, PKMixin, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_tenant", "tenant_id", "status"),)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("bot_users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.new, nullable=False
    )
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    payment_id: Mapped[str | None] = mapped_column(String(255))
    comment: Mapped[str | None] = mapped_column(Text)
    shipping: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base, PKMixin):
    __tablename__ = "order_items"

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    order: Mapped[Order] = relationship(back_populates="items")


# ---------------------------------------------------------------------------
# Запись на услуги (booking)
# ---------------------------------------------------------------------------


class Service(Base, PKMixin, TimestampMixin):
    __tablename__ = "services"
    __table_args__ = (Index("ix_services_tenant", "tenant_id"),)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    duration_min: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BookingStatus(enum.StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    done = "done"


class Booking(Base, PKMixin, TimestampMixin):
    __tablename__ = "bookings"
    __table_args__ = (
        Index("ix_bookings_tenant_time", "tenant_id", "starts_at"),
    )

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("bot_users.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus), default=BookingStatus.pending, nullable=False
    )
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    service: Mapped[Service] = relationship()


# ---------------------------------------------------------------------------
# Поддержка (тикеты)
# ---------------------------------------------------------------------------


class TicketStatus(enum.StrEnum):
    open = "open"
    pending = "pending"
    closed = "closed"


class Ticket(Base, PKMixin, TimestampMixin):
    __tablename__ = "tickets"
    __table_args__ = (Index("ix_tickets_tenant", "tenant_id", "status"),)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("bot_users.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus), default=TicketStatus.open, nullable=False
    )
    assigned_operator: Mapped[int | None] = mapped_column(BigInteger)

    messages: Mapped[list[TicketMessage]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class TicketMessage(Base, PKMixin, TimestampMixin):
    __tablename__ = "ticket_messages"

    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    from_operator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped[Ticket] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# CRM и рассылки
# ---------------------------------------------------------------------------


class BroadcastStatus(enum.StrEnum):
    draft = "draft"
    scheduled = "scheduled"
    sending = "sending"
    done = "done"
    cancelled = "cancelled"


class Broadcast(Base, PKMixin, TimestampMixin):
    __tablename__ = "broadcasts"
    __table_args__ = (Index("ix_broadcasts_tenant", "tenant_id", "status"),)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String(1024))
    # Простой сегмент-фильтр, напр. {"has_order": true}
    segment: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    status: Mapped[BroadcastStatus] = mapped_column(
        Enum(BroadcastStatus), default=BroadcastStatus.draft, nullable=False
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
