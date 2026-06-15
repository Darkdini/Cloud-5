"""Pydantic-схемы для админ-API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    title: str
    bot_token: str
    bot_username: str | None = None
    locale: str = "ru"
    enabled_modules: list[str] = Field(default_factory=list)
    settings: dict = Field(default_factory=dict)


class TenantUpdate(BaseModel):
    title: str | None = None
    is_active: bool | None = None
    enabled_modules: list[str] | None = None
    settings: dict | None = None


class TenantOut(BaseModel):
    id: int
    title: str
    bot_username: str | None
    is_active: bool
    locale: str
    enabled_modules: list[str]

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    title: str
    sort_order: int = 0


class ProductCreate(BaseModel):
    title: str
    description: str | None = None
    price: int  # в минорных единицах (копейки)
    currency: str = "RUB"
    category_id: int | None = None
    photo_url: str | None = None
    stock: int | None = None


class ServiceCreate(BaseModel):
    title: str
    description: str | None = None
    duration_min: int = 60
    price: int = 0


class KnowledgeCreate(BaseModel):
    title: str
    content: str


class BroadcastCreate(BaseModel):
    title: str
    text: str
    photo_url: str | None = None
    segment: dict = Field(default_factory=dict)


class IdOut(BaseModel):
    id: int


class TenantStats(BaseModel):
    users: int
    orders: int
    revenue: int
    bookings: int
    open_tickets: int


class BroadcastResult(BaseModel):
    sent: int
    failed: int


class MessageOut(BaseModel):
    detail: str


class HealthOut(BaseModel):
    status: str
    time: datetime
