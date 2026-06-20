import Link from "next/link";
import { prisma } from "@/lib/db";
import { Hero } from "@/components/hero";
import { Reveal } from "@/components/reveal";
import { ProductCard } from "@/components/product-card";
import { CatIcon, ACCENT } from "@/components/icon";
import { ShieldCheck, Rocket, CreditCard } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [categories, featured, total] = await Promise.all([
    prisma.category.findMany({
      include: { _count: { select: { products: true } } },
      orderBy: { title: "asc" },
    }),
    prisma.product.findMany({
      where: { featured: true },
      include: { category: true },
      take: 6,
      orderBy: { sales: "desc" },
    }),
    prisma.product.count(),
  ]);

  return (
    <>
      <Hero productCount={total} />

      {/* Разделы */}
      <section id="sections" className="container-x py-12">
        <Reveal>
          <h2 className="font-display text-2xl font-bold sm:text-3xl">
            Разделы площадки
          </h2>
          <p className="mt-1 text-white/50">Выбери, что тебе нужно</p>
        </Reveal>

        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {categories.map((c, i) => {
            const accent = ACCENT[c.accent] ?? ACCENT.violet;
            return (
              <Reveal key={c.id} delay={i * 0.06}>
                <Link
                  href={`/catalog?cat=${c.slug}`}
                  className="glass group flex h-full flex-col gap-3 p-6 transition hover:-translate-y-1"
                >
                  <div className={`grid h-12 w-12 place-items-center rounded-xl bg-white/5 ${accent.text}`}>
                    <CatIcon name={c.icon} className="h-6 w-6" />
                  </div>
                  <h3 className="font-display text-lg font-semibold">{c.title}</h3>
                  <p className="text-sm text-white/45">
                    {c._count.products} товаров
                  </p>
                </Link>
              </Reveal>
            );
          })}
        </div>
      </section>

      {/* Хиты */}
      <section className="container-x py-12">
        <Reveal>
          <div className="flex items-end justify-between">
            <div>
              <h2 className="font-display text-2xl font-bold sm:text-3xl">Хиты продаж</h2>
              <p className="mt-1 text-white/50">Лучшее на площадке прямо сейчас</p>
            </div>
            <Link href="/catalog" className="btn-ghost hidden sm:inline-flex">
              Весь каталог
            </Link>
          </div>
        </Reveal>

        <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {featured.map((p, i) => (
            <ProductCard key={p.id} p={p} index={i} />
          ))}
        </div>
      </section>

      {/* Как это работает */}
      <section id="how" className="container-x py-12">
        <Reveal>
          <h2 className="font-display text-2xl font-bold sm:text-3xl">Как это работает</h2>
        </Reveal>
        <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-3">
          {[
            { icon: Rocket, t: "Регистрируйся", d: "Создай аккаунт за минуту — email и пароль." },
            { icon: CreditCard, t: "Выбирай и покупай", d: "Оплата звёздами, мгновенный доступ к товару." },
            { icon: ShieldCheck, t: "Получай доступ", d: "Все покупки хранятся в твоей библиотеке." },
          ].map((s, i) => (
            <Reveal key={s.t} delay={i * 0.08}>
              <div className="glass h-full p-6">
                <div className="mb-4 grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-neon-violet to-neon-cyan text-white shadow-glow">
                  <s.icon className="h-6 w-6" />
                </div>
                <h3 className="font-display text-lg font-semibold">{s.t}</h3>
                <p className="mt-1 text-sm text-white/50">{s.d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>
    </>
  );
}
