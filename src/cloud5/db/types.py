"""Кросс-СУБД типы колонок.

Позволяют одной схеме работать и на PostgreSQL (продакшен), и на SQLite
(локально / Termux на телефоне, без отдельной БД).
"""

from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Integer
from sqlalchemy.dialects.postgresql import JSONB

# JSON: нативный JSONB на Postgres, обычный JSON на SQLite
JSONType = JSON().with_variant(JSONB, "postgresql")

# Автоинкрементный первичный ключ: BIGINT на Postgres, INTEGER на SQLite
# (SQLite автоинкремент работает только с INTEGER PRIMARY KEY)
BigIntPK = BigInteger().with_variant(Integer, "sqlite")
