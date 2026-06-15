# Запуск Cloud-5 на телефоне (Termux)

Компьютер не нужен — платформа поднимается прямо на Android в режиме SQLite
(файловая база) и polling. PostgreSQL и Redis не требуются.

## 1. Установить Termux

Поставьте Termux из **F-Droid** (версия из Google Play устарела).

## 2. Поставить зависимости

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git rust binutils
```

> `rust` и `binutils` нужны, чтобы собрать пару Python-пакетов на телефоне.

## 3. Скачать проект

```bash
git clone <URL-репозитория> Cloud-5
cd Cloud-5
git checkout claude/telegram-business-bots-yq3y46
```

## 4. Установить и настроить

```bash
pip install -e .
cp .env.termux.example .env
```

Откройте `.env` (`nano .env`) и при желании впишите `ANTHROPIC_API_KEY`
для ИИ-ассистента. Без ключа остальные модули (магазин, запись, поддержка)
работают как обычно.

## 5. Создать базу и подключить бота

Токен берётся у [@BotFather](https://t.me/BotFather).

```bash
python -m cloud5.cli init-db
python -m cloud5.cli add-tenant \
  --title "Мой бизнес" \
  --token 123456:ABC-ваш-токен \
  --modules ai_assistant,shop,booking,support
```

## 6. Запустить

```bash
python -m cloud5.bot.main
```

Откройте своего бота в Telegram и нажмите **/start**. Готово 🎉

## Чтобы бот не отключался

- Отключите для Termux экономию батареи в настройках Android.
- Держите Termux в режиме wake-lock:
  ```bash
  termux-wake-lock
  ```
- Опционально поставьте `pkg install termux-services`, чтобы запускать в фоне.

## Когда перерастёте телефон

Тот же код без изменений работает на сервере с PostgreSQL + Redis —
достаточно поменять `DATABASE_URL` и `REDIS_URL` в `.env` и запустить
`docker compose up`. Данные переносятся миграциями Alembic.

## Если что-то не ставится

- Драйвер PostgreSQL (`asyncpg`) вынесен в отдельный extra `[postgres]` и на
  телефоне **не ставится** — SQLite работает через `aiosqlite` без сборки.
- При ошибке сборки `pydantic-core` обновите Rust: `pkg upgrade rust`.
