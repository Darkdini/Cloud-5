import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

const CATEGORIES = [
  { slug: "bots", title: "Телеграм-боты", icon: "bot", accent: "cyan" },
  { slug: "games", title: "Исходники игр", icon: "gamepad", accent: "violet" },
  { slug: "scripts", title: "Скрипты/Шаблоны", icon: "code", accent: "lime" },
  { slug: "assets", title: "Дизайн/ассеты", icon: "palette", accent: "pink" },
];

const PRODUCTS = [
  {
    slug: "donate-stars-bot",
    cat: "bots",
    title: "Донат-бот на звёздах",
    tagline: "Принимай донаты Telegram Stars и веди Доску почёта спонсоров.",
    description:
      "Готовый бот на Python (aiogram)\nКнопки сумм 100/200/300/400/1000 ⭐\nКарточка донатера с ником и оформлением\nАвтопост в группу-доску почёта\nАдмин-панель и тест без оплаты",
    priceStars: 1500,
    badge: "HOT",
    featured: true,
    rating: 5,
    sales: 128,
  },
  {
    slug: "shop-bot-pro",
    cat: "bots",
    title: "Магазин-бот PRO",
    tagline: "Каталог, корзина, оплата картой и звёздами, админка.",
    description:
      "Категории и товары\nКорзина и оформление заказа\nОплата картой/звёздами\nУведомления оператору",
    priceStars: 2500,
    badge: "NEW",
    featured: true,
    rating: 5,
    sales: 74,
  },
  {
    slug: "booking-bot",
    cat: "bots",
    title: "Бот записи на услуги",
    tagline: "Онлайн-запись с выбором дня и слота, напоминания.",
    description: "Услуги и расписание\nВыбор дня и времени\nНапоминания клиентам",
    priceStars: 1800,
    badge: "",
    featured: false,
    rating: 4,
    sales: 41,
  },
  {
    slug: "platformer-source",
    cat: "games",
    title: "2D-платформер (исходник)",
    tagline: "Полный исходник аркадного платформера на Unity.",
    description:
      "Проект Unity 2022+\nУровни, враги, физика\nМеню и сохранения\nКомментарии в коде",
    priceStars: 3200,
    badge: "TOP",
    featured: true,
    rating: 5,
    sales: 56,
  },
  {
    slug: "match3-source",
    cat: "games",
    title: "Match-3 головоломка",
    tagline: "Три в ряд: исходник с бустерами и уровнями.",
    description: "Готовая механика три-в-ряд\nБустеры и комбо\nЭкономика и магазин",
    priceStars: 2700,
    badge: "",
    featured: false,
    rating: 5,
    sales: 33,
  },
  {
    slug: "tg-mini-game",
    cat: "games",
    title: "Telegram Mini-App игра",
    tagline: "Кликер-игра для Telegram Mini Apps на React.",
    description: "React + TON-ready\nЛидерборд\nЕжедневные награды",
    priceStars: 2200,
    badge: "NEW",
    featured: true,
    rating: 4,
    sales: 60,
  },
  {
    slug: "parser-script",
    cat: "scripts",
    title: "Парсер маркетплейсов",
    tagline: "Скрипт сбора цен и товаров на Python.",
    description: "Асинхронный сбор\nЭкспорт в CSV/Excel\nПрокси и капча-обход",
    priceStars: 1200,
    badge: "",
    featured: false,
    rating: 5,
    sales: 88,
  },
  {
    slug: "saas-landing",
    cat: "scripts",
    title: "SaaS лендинг-шаблон",
    tagline: "Next.js шаблон лендинга с анимациями.",
    description: "Next.js + Tailwind\nАнимации и тёмная тема\nФорма заявки",
    priceStars: 1600,
    badge: "HOT",
    featured: true,
    rating: 5,
    sales: 95,
  },
  {
    slug: "ui-kit-neon",
    cat: "assets",
    title: "Neon UI Kit",
    tagline: "200+ компонентов в неоновом стиле для Figma.",
    description: "Figma-библиотека\nТёмная/светлая темы\nАвтолейаут",
    priceStars: 1400,
    badge: "",
    featured: false,
    rating: 5,
    sales: 47,
  },
  {
    slug: "game-sprites-pack",
    cat: "assets",
    title: "Пак игровых спрайтов",
    tagline: "500+ спрайтов: персонажи, тайлы, иконки.",
    description: "PNG + исходники\nАнимационные кадры\nКоммерческая лицензия",
    priceStars: 900,
    badge: "NEW",
    featured: false,
    rating: 4,
    sales: 52,
  },
];

async function main() {
  for (const c of CATEGORIES) {
    await prisma.category.upsert({
      where: { slug: c.slug },
      create: c,
      update: { title: c.title, icon: c.icon, accent: c.accent },
    });
  }

  const cats = await prisma.category.findMany();
  const bySlug = Object.fromEntries(cats.map((c) => [c.slug, c.id]));

  for (const p of PRODUCTS) {
    const { cat, ...rest } = p;
    await prisma.product.upsert({
      where: { slug: p.slug },
      create: { ...rest, categoryId: bySlug[cat] },
      update: { ...rest, categoryId: bySlug[cat] },
    });
  }

  // Демо-аккаунт для входа
  await prisma.user.upsert({
    where: { email: "demo@cloud5.app" },
    create: {
      email: "demo@cloud5.app",
      name: "Demo",
      passwordHash: await bcrypt.hash("demo123", 10),
    },
    update: {},
  });

  console.log("✅ Сид готов: 4 раздела,", PRODUCTS.length, "товаров, demo@cloud5.app / demo123");
}

main()
  .then(() => prisma.$disconnect())
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
