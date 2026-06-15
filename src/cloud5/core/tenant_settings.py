"""Изменение настроек тенанта на лету.

Обновляет настройки и в БД, и в in-memory снапшоте реестра — чтобы правки из
админ-панели внутри бота применялись сразу, без перезапуска рантайма.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from cloud5.config import settings
from cloud5.core.registry import TenantInfo
from cloud5.db.models import Tenant


async def patch_module_settings(
    session: AsyncSession, tenant: TenantInfo, module: str, patch: dict
) -> None:
    """Слить ``patch`` в settings[module] тенанта (БД + реестр)."""
    db_tenant = await session.get(Tenant, tenant.id)
    if db_tenant is None:
        return
    # новый dict, чтобы SQLAlchemy заметил изменение JSON-поля
    settings = dict(db_tenant.settings or {})
    module_cfg = dict(settings.get(module, {}))
    module_cfg.update(patch)
    settings[module] = module_cfg
    db_tenant.settings = settings
    await session.flush()
    tenant.settings = settings  # синхронизируем «живой» снапшот


def is_admin(tenant: TenantInfo, telegram_id: int) -> bool:
    if telegram_id in settings.admin_ids_list:
        return True  # глобальный админ
    ids = (tenant.settings.get("admin", {}) or {}).get("ids", [])
    return telegram_id in ids
