"""CLI управления донат-ботом.

Примеры:
    python -m cloud5.cli init-db
    python -m cloud5.cli add-tenant --title "Донат" --token 123:ABC
    python -m cloud5.cli setup-donate --tenant-id 1 --amounts 100,200,300,400,1000
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


async def _add_tenant(title: str, token: str, username: str | None) -> None:
    async with session_scope() as session:
        tenant = Tenant(
            title=title,
            bot_token=token,
            bot_username=username,
            enabled_modules=["donate"],
            settings={"donate": {"amounts": [100, 200, 300, 400, 1000], "amount_xtr": 100}},
        )
        session.add(tenant)
        await session.flush()
        print(
            f"✅ Бот #{tenant.id} «{title}» создан (режим доната).\n"
            "Запуск:  python -m cloud5.bot.main"
        )


async def _list_tenants() -> None:
    async with session_scope() as session:
        rows = (await session.execute(select(Tenant).order_by(Tenant.id))).scalars().all()
        if not rows:
            print("Ботов пока нет.")
            return
        for t in rows:
            status = "🟢" if t.is_active else "⚪️"
            amounts = (t.settings or {}).get("donate", {}).get("amounts", [])
            print(f"{status} #{t.id} {t.title} — суммы: {amounts}")


async def _add_admin(tenant_id: int, telegram_id: int) -> None:
    async with session_scope() as session:
        tenant = await session.get(Tenant, tenant_id)
        if tenant is None:
            print("Бот не найден")
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


async def _setup_donate(tenant_id: int, amounts: list[int]) -> None:
    """Настроить кнопки сумм доната."""
    amounts = [a for a in amounts if a >= 1] or [100]
    async with session_scope() as session:
        tenant = await session.get(Tenant, tenant_id)
        if tenant is None:
            print("Бот не найден")
            return
        tenant.enabled_modules = ["donate"]
        settings = dict(tenant.settings or {})
        donate_cfg = dict(settings.get("donate", {}))
        donate_cfg["amounts"] = amounts
        donate_cfg["amount_xtr"] = amounts[0]
        settings["donate"] = donate_cfg
        tenant.settings = settings
        pretty = ", ".join(f"{a}⭐" for a in amounts)
        print(
            f"✅ Бот #{tenant_id}: кнопки сумм — {pretty}\n"
            "Перезапусти бота и в группе-доске отправь /setwall."
        )


def main() -> None:
    parser = argparse.ArgumentParser(prog="cloud5")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="создать таблицы")

    p_add = sub.add_parser("add-tenant", help="добавить бота")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--token", required=True)
    p_add.add_argument("--username", default=None)

    sub.add_parser("list-tenants", help="список ботов")

    p_adm = sub.add_parser("add-admin", help="назначить админа бота (для /admin)")
    p_adm.add_argument("--tenant-id", type=int, required=True)
    p_adm.add_argument("--telegram-id", type=int, required=True)

    p_don = sub.add_parser("setup-donate", help="настроить кнопки сумм доната")
    p_don.add_argument("--tenant-id", type=int, required=True)
    p_don.add_argument(
        "--amounts",
        default="100,200,300,400,1000",
        help="суммы через запятую, напр. 100,200,300,400,1000",
    )

    args = parser.parse_args()
    init_engine()

    if args.cmd == "init-db":
        asyncio.run(_init_db())
    elif args.cmd == "add-tenant":
        asyncio.run(_add_tenant(args.title, args.token, args.username))
    elif args.cmd == "list-tenants":
        asyncio.run(_list_tenants())
    elif args.cmd == "add-admin":
        asyncio.run(_add_admin(args.tenant_id, args.telegram_id))
    elif args.cmd == "setup-donate":
        amounts = [int(x) for x in args.amounts.split(",") if x.strip().isdigit()]
        asyncio.run(_setup_donate(args.tenant_id, amounts))


if __name__ == "__main__":
    main()
