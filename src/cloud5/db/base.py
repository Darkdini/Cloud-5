"""Базовый класс моделей и общие миксины."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from cloud5.db.types import BigIntPK


class Base(DeclarativeBase):
    """Базовый декларативный класс для всех моделей."""


class TimestampMixin:
    """Добавляет поля created_at / updated_at."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PKMixin:
    """Числовой первичный ключ."""

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
