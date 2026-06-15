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

from sqlalchemy import select

from cloud5.db.base import Base
from cloud5.db.models import Tenant
from cloud5.db.session import init_engine, session_scope


async def _init_db() -> None:
    engine = init_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Таблицы созданы")


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


def main() -> None:
    parser = argparse.ArgumentParser(prog="cloud5")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="создать таблицы")

    p_add = sub.add_parser("add-tenant", help="добавить бота клиента")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--token", required=True)
    p_add.add_argument("--username", default=None)
    p_add.add_argument("--modules", default="")

    sub.add_parser("list-tenants", help="список ботов")

    p_en = sub.add_parser("enable-module", help="включить модуль")
    p_en.add_argument("--tenant-id", type=int, required=True)
    p_en.add_argument("--module", required=True)

    args = parser.parse_args()
    init_engine()

    if args.cmd == "init-db":
        asyncio.run(_init_db())
    elif args.cmd == "add-tenant":
        asyncio.run(_add_tenant(args.title, args.token, args.modules, args.username))
    elif args.cmd == "list-tenants":
        asyncio.run(_list_tenants())
    elif args.cmd == "enable-module":
        asyncio.run(_enable_module(args.tenant_id, args.module))


if __name__ == "__main__":
    main()
