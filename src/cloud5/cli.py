"""CLI управления платформой: тенанты, модули, инициализация БД.

Примеры:
    python -m cloud5.cli init-db
    python -m cloud5.cli add-tenant --title "Кофейня" --token 123:ABC \\
        --modules ai_assistant,shop
    python -m cloud5.cli list-tenants
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, select

from cloud5.db.base import Base
from cloud5.db.models import (
    Category,
    KnowledgeDoc,
    Product,
    Service,
    Tenant,
)
from cloud5.db.session import init_engine, session_scope


async def _init_db() -> None:
    engine = init_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Таблицы созданы")


async def _quickstart() -> None:
    """Всё за один шаг: таблицы + тестовый бот + демо-данные."""
    from cloud5.config import settings

    await _init_db()
    async with session_scope() as session:
        existing = (
            await session.execute(
                select(Tenant).where(Tenant.bot_token == settings.default_bot_token)
            )
        ).scalar_one_or_none()
        if existing is None:
            mods = [m.strip() for m in settings.default_modules.split(",") if m.strip()]
            tenant = Tenant(
                title=settings.default_bot_title,
                bot_token=settings.default_bot_token,
                enabled_modules=mods,
                settings={},
            )
            session.add(tenant)
            await session.flush()
            tenant_id = tenant.id
            print(f"✅ Бот #{tenant_id} «{settings.default_bot_title}» создан.")
        else:
            tenant_id = existing.id
            print(f"ℹ️  Бот #{tenant_id} уже существует, пропускаю создание.")

    await _seed(tenant_id)
    print("\n🎉 Готово! Запуск:  python -m cloud5.bot.main")


async def _add_tenant(title: str, token: str, modules: str, username: str | None) -> None:
    mod_list = [m.strip() for m in modules.split(",") if m.strip()]
    async with session_scope() as session:
        tenant = Tenant(
            title=title,
            bot_token=token,
            bot_username=username,
            enabled_modules=mod_list,
            settings={},
        )
        session.add(tenant)
        await session.flush()
        print(f"✅ Тенант #{tenant.id} «{title}» создан. Модули: {mod_list}")


async def _list_tenants() -> None:
    async with session_scope() as session:
        rows = (await session.execute(select(Tenant).order_by(Tenant.id))).scalars().all()
        if not rows:
            print("Тенантов пока нет.")
            return
        for t in rows:
            status = "🟢" if t.is_active else "⚪️"
            print(f"{status} #{t.id} {t.title} — модули: {t.enabled_modules}")


async def _enable_module(tenant_id: int, module: str) -> None:
    async with session_scope() as session:
        tenant = await session.get(Tenant, tenant_id)
        if tenant is None:
            print("Тенант не найден")
            return
        mods = set(tenant.enabled_modules or [])
        mods.add(module)
        tenant.enabled_modules = sorted(mods)
        print(f"✅ Модуль {module} включён для #{tenant_id}")


async def _add_admin(tenant_id: int, telegram_id: int) -> None:
    async with session_scope() as session:
        tenant = await session.get(Tenant, tenant_id)
        if tenant is None:
            print("Тенант не найден")
            return
        settings = dict(tenant.settings or {})
        admin_cfg = dict(settings.get("admin", {}))
        ids = set(admin_cfg.get("ids", []))
        ids.add(telegram_id)
        admin_cfg["ids"] = sorted(ids)
        settings["admin"] = admin_cfg
        tenant.settings = settings
        print(
            f"✅ Админ {telegram_id} назначен для #{tenant_id}. "
            "В боте доступна команда /admin"
        )


# Демо-наполнение для показа клиентам
DEMO_CATEGORIES = {
    "☕️ Кофе": [
        ("Капучино", "Классический на цельном молоке", 18000),
        ("Латте", "Нежный, с большим количеством молока", 19000),
        ("Раф ванильный", "Сливочный раф с ванилью", 22000),
    ],
    "🥐 Выпечка": [
        ("Круассан", "Хрустящий, свежая выпечка", 12000),
        ("Чизкейк", "Нью-Йорк, кусочек", 25000),
    ],
}
DEMO_SERVICES = [
    ("Мужская стрижка", "Стрижка машинкой и ножницами", 30, 80000),
    ("Стрижка бороды", "Моделирование и оформление", 30, 50000),
    ("Комплекс", "Стрижка + борода", 60, 110000),
]
DEMO_KNOWLEDGE = (
    "О компании",
    "Мы работаем ежедневно с 10:00 до 21:00. Доставка по городу за 1 час, "
    "от 1500 ₽ — бесплатно. Принимаем оплату картой и наличными. "
    "Адрес: ул. Примерная, 1. Телефон: +7 900 000-00-00.",
)


async def _seed(tenant_id: int) -> None:
    async with session_scope() as session:
        tenant = await session.get(Tenant, tenant_id)
        if tenant is None:
            print("Тенант не найден")
            return

        existing = await session.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.tenant_id == tenant_id)
        )
        if existing:
            print(f"⚠️  У тенанта #{tenant_id} уже есть товары — пропускаю сидер.")
            return

        for cat_title, products in DEMO_CATEGORIES.items():
            category = Category(tenant_id=tenant_id, title=cat_title)
            session.add(category)
            await session.flush()
            for title, desc, price in products:
                session.add(
                    Product(
                        tenant_id=tenant_id,
                        category_id=category.id,
                        title=title,
                        description=desc,
                        price=price,
                        currency="RUB",
                    )
                )

        for title, desc, duration, price in DEMO_SERVICES:
            session.add(
                Service(
                    tenant_id=tenant_id,
                    title=title,
                    description=desc,
                    duration_min=duration,
                    price=price,
                )
            )

        k_title, k_content = DEMO_KNOWLEDGE
        session.add(
            KnowledgeDoc(tenant_id=tenant_id, title=k_title, content=k_content)
        )

    print(
        f"✅ Демо-данные добавлены для #{tenant_id}: "
        "категории, товары, услуги и база знаний."
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="cloud5")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="создать таблицы")
    sub.add_parser("quickstart", help="всё за раз: БД + тестовый бот + демо-данные")

    p_add = sub.add_parser("add-tenant", help="добавить бота клиента")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--token", required=True)
    p_add.add_argument("--username", default=None)
    p_add.add_argument("--modules", default="")

    sub.add_parser("list-tenants", help="список ботов")

    p_en = sub.add_parser("enable-module", help="включить модуль")
    p_en.add_argument("--tenant-id", type=int, required=True)
    p_en.add_argument("--module", required=True)

    p_seed = sub.add_parser("seed", help="заполнить демо-данными для показа")
    p_seed.add_argument("--tenant-id", type=int, required=True)

    p_adm = sub.add_parser("add-admin", help="назначить админа бота (для /admin)")
    p_adm.add_argument("--tenant-id", type=int, required=True)
    p_adm.add_argument("--telegram-id", type=int, required=True)

    args = parser.parse_args()
    init_engine()

    if args.cmd == "init-db":
        asyncio.run(_init_db())
    elif args.cmd == "quickstart":
        asyncio.run(_quickstart())
    elif args.cmd == "add-tenant":
        asyncio.run(_add_tenant(args.title, args.token, args.modules, args.username))
    elif args.cmd == "list-tenants":
        asyncio.run(_list_tenants())
    elif args.cmd == "enable-module":
        asyncio.run(_enable_module(args.tenant_id, args.module))
    elif args.cmd == "seed":
        asyncio.run(_seed(args.tenant_id))
    elif args.cmd == "add-admin":
        asyncio.run(_add_admin(args.tenant_id, args.telegram_id))


if __name__ == "__main__":
    main()
