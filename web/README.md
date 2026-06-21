# Cloud-5 · Маркетплейс (web)

Футуристичная торговая площадка: телеграм-боты, исходники игр, скрипты и ассеты.
Регистрация/вход, разделы, карточки товаров, библиотека покупок.

**Стек:** Next.js 15 (App Router) · TypeScript · Tailwind CSS · Framer Motion ·
Prisma · кастомная JWT-авторизация (jose + bcrypt).

## Локальный запуск

Нужна база PostgreSQL (бесплатно — на [neon.tech](https://neon.tech)).

```bash
cd web
npm install
cp .env.example .env          # впиши DATABASE_URL (Postgres) и AUTH_SECRET
npx prisma db push            # создать таблицы
npm run db:seed               # демо-разделы и товары
npm run dev                   # http://localhost:3000
```

Демо-аккаунт: **demo@cloud5.app / demo123** (или зарегистрируй новый).

> ⚠️ На телефоне (Termux) сайт не запустится: у Prisma нет движка под Android.
> Сайт рассчитан на Vercel + Postgres (см. ниже). На телефоне держим только бота.

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

## Деплой на Vercel (пошагово)

**1. База данных (Neon, бесплатно):**
- Зайди на [neon.tech](https://neon.tech) → войди через GitHub → создай проект.
- Скопируй **Connection string** (вида `postgresql://...:...@...neon.tech/...?sslmode=require`).

**2. Проект на Vercel:**
- [vercel.com](https://vercel.com) → войди через GitHub → **Add New → Project**.
- Выбери репозиторий `Darkdini/cloud-5`.
- **Root Directory** → нажми Edit и укажи **`web`**.
- Framework определится как Next.js автоматически.

**3. Переменные окружения** (Environment Variables в настройках проекта):
- `DATABASE_URL` = строка из Neon
- `AUTH_SECRET` = любая длинная случайная строка

**4. Deploy.**
Сборка запустит скрипт `vercel-build`: сгенерирует Prisma-клиент, **создаст
таблицы** в твоей базе, **зальёт демо-данные** и соберёт сайт. После деплоя
получишь адрес вида `cloud5.vercel.app`.

> Схема и сид применяются автоматически при каждом деплое (операции
> идемпотентные — данные не дублируются). Когда добавишь реальные товары,
> можно убрать `tsx prisma/seed.ts` из `vercel-build`, чтобы не пересоздавать демо.

## Дальше (roadmap)

- Реальная оплата (Telegram Stars / карта) вместо демо-покупки
- Загрузка/выдача файлов товара после покупки
- Кабинет автора: добавление своих товаров
- Поиск, сортировка, отзывы
