# Cloud-5 · Маркетплейс (web)

Футуристичная торговая площадка: телеграм-боты, исходники игр, скрипты и ассеты.
Регистрация/вход, разделы, карточки товаров, библиотека покупок.

**Стек:** Next.js 15 (App Router) · TypeScript · Tailwind CSS · Framer Motion ·
Prisma · кастомная JWT-авторизация (jose + bcrypt).

## Локальный запуск

```bash
cd web
npm install
cp .env.example .env          # DATABASE_URL=file:./dev.db уже подойдёт
npx prisma db push            # создать таблицы
npm run db:seed               # демо-разделы и товары
npm run dev                   # http://localhost:3000
```

Демо-аккаунт: **demo@cloud5.app / demo123** (или зарегистрируй новый).

## Структура

```
src/
  app/                # страницы (App Router) и API-роуты
    page.tsx          # главная (hero, разделы, хиты)
    catalog/          # каталог с фильтром по разделам
    product/[slug]/   # карточка товара + покупка
    login, register   # авторизация
    dashboard/        # личный кабинет (библиотека покупок)
    api/auth/*        # register / login / logout
    api/purchase      # оформление покупки (защищено)
  components/          # Header, Hero, ProductCard, AuthForm, фон и т.д.
  lib/                # db (Prisma), auth (JWT), validation (zod)
prisma/
  schema.prisma       # User, Category, Product, Purchase
  seed.ts             # демо-данные
```

## Деплой на Vercel

1. Запушь репозиторий в GitHub (папка `web/` как корень проекта Vercel,
   либо настрой Root Directory = `web`).
2. В `prisma/schema.prisma` смени `provider = "sqlite"` на `"postgresql"`.
3. Подключи Vercel Postgres / Neon и задай переменные окружения:
   - `DATABASE_URL` — строка подключения Postgres
   - `AUTH_SECRET` — длинная случайная строка
4. Команда сборки уже включает `prisma generate` (см. `package.json`).
   После первого деплоя выполни миграцию схемы: `npx prisma db push`
   (локально на прод-БД) или добавь шаг в пайплайн.

> Локально используется SQLite — на Vercel serverless файловая система
> эфемерна, поэтому для продакшена нужен внешний Postgres.

## Дальше (roadmap)

- Реальная оплата (Telegram Stars / карта) вместо демо-покупки
- Загрузка/выдача файлов товара после покупки
- Кабинет автора: добавление своих товаров
- Поиск, сортировка, отзывы
