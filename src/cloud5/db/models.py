"""Доменные модели донат-бота Cloud-5.

Всё привязано к тенанту (боту) через ``tenant_id`` — полная изоляция данных
между разными ботами на одном движке.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cloud5.db.base import Base, PKMixin, TimestampMixin
from cloud5.db.types import JSONType


class Tenant(Base, PKMixin, TimestampMixin):
    """Один бот клиента. Хранит токен и настройки."""

    __tablename__ = "tenants"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    bot_token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    bot_username: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)

    # Список включённых модулей (для донат-бота — ["donate"])
    enabled_modules: Mapped[list[str]] = mapped_column(
        JSONType, default=list, nullable=False
    )
    # Настройки модулей: {"donate": {"amounts": [...], "wall_chat_id": ...}}
    settings: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    users: Mapped[list[BotUser]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )

    def module_settings(self, module: str) -> dict:
        return (self.settings or {}).get(module, {})

    def has_module(self, module: str) -> bool:
        return module in (self.enabled_modules or [])


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


class Donation(Base, PKMixin, TimestampMixin):
    """Донат пользователя звёздами. Попадает в «Доску почёта»."""

    __tablename__ = "donations"
    __table_args__ = (Index("ix_donations_tenant", "tenant_id", "id"),)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("bot_users.id", ondelete="CASCADE"), nullable=False
    )
    amount_xtr: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    charge_id: Mapped[str | None] = mapped_column(String(255))
    posted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
