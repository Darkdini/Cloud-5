# Cloud-5 — Telegram Business Bots Platform

Мульти-тенантная платформа для запуска **бизнес-ботов в Telegram**. Один движок
крутит сразу много ботов клиентов, каждый со своей конфигурацией и данными в БД.

Продукт рассчитан на продажу: подключаешь токен бота клиента → включаешь нужные
модули → бот зарабатывает.

## Возможности (модули)

| Модуль | Что делает |
|---|---|
| 🧠 `ai_assistant` | ИИ-консультант/продажник на Claude. Помнит историю диалога (в БД), отвечает по базе знаний клиента. |
| 🛒 `shop` | Каталог, корзина, заказы, оплата через Telegram Payments. |
| 📅 `booking` | Запись на услуги: слоты, бронирование, напоминания. |
| 🎫 `support` | Тикеты поддержки, маршрутизация на операторов. |
| 📣 `crm` | Лиды, сегменты, массовые рассылки. |

## Стек

- **Python 3.11**, [aiogram 3](https://docs.aiogram.dev/) — Telegram-фреймворк
- **PostgreSQL** + **SQLAlchemy 2 (async)** + **Alembic** — хранение всех данных
- **Redis** — FSM-состояния и кэш
- **FastAPI** — админ-API
- **Anthropic Claude** — ИИ-модуль
- **Docker Compose** — запуск одной командой

## Архитектура

```
                       ┌──────────────────────────┐
                       │      Cloud-5 Runtime      │
                       │  (один процесс, N ботов)  │
   Telegram  ───────►  │  ┌────────┐  ┌────────┐   │
   (webhook/poll)      │  │ Bot #1 │  │ Bot #N │…  │
                       │  └───┬────┘  └───┬────┘   │
                       └──────┼───────────┼────────┘
                              ▼           ▼
                       ┌──────────────────────────┐
                       │   Модули (per-tenant)     │
                       │  ai · shop · booking …    │
                       └──────────────┬───────────┘
                                      ▼
                       ┌──────────────────────────┐
                       │   PostgreSQL  ·  Redis    │
                       └──────────────────────────┘
```

Каждый бот клиента = строка `Tenant` в БД с токеном и набором включённых модулей.
Все клиенты, заказы, диалоги, лиды изолированы по `tenant_id`.

## Быстрый старт

```bash
cp .env.example .env          # впишите ключи
docker compose up -d db redis # поднять БД и Redis
make migrate                  # применить миграции
make run                      # запустить рантайм ботов
make api                      # (опц.) запустить админ-API
```

Локально без Docker:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m cloud5.bot.main
```

## Добавить нового бота клиента

```bash
python -m cloud5.cli add-tenant \
  --title "Кофейня у дома" \
  --token 123456:ABC... \
  --modules ai_assistant,shop
```

## Структура

```
src/cloud5/
  config.py        # настройки (pydantic-settings)
  db/              # модели и сессии SQLAlchemy
  core/            # рантайм мульти-тенант, реестр, i18n
  modules/         # бизнес-модули (ai, shop, booking, support, crm)
  services/        # ИИ, платежи, рассылки
  admin/           # FastAPI админ-API
  bot/main.py      # точка входа рантайма
  cli.py           # управление тенантами из консоли
```

## Лицензия

Proprietary © Cloud-5. Коммерческий продукт.
