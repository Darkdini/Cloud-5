import Link from "next/link";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/db";
import { getSessionUser } from "@/lib/auth";
import { Reveal } from "@/components/reveal";
import { CatIcon, ACCENT } from "@/components/icon";
import { Library, Star } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  const purchases = await prisma.purchase.findMany({
    where: { userId: user.id },
    include: { product: { include: { category: true } } },
    orderBy: { createdAt: "desc" },
  });

  return (
    <div className="container-x py-12">
      <Reveal>
        <div className="glass flex items-center gap-4 p-6">
          <div className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-neon-violet to-neon-cyan text-xl font-bold text-white shadow-glow">
            {user.name.charAt(0).toUpperCase()}
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold">{user.name}</h1>
            <p className="text-sm text-white/50">{user.email}</p>
          </div>
        </div>
      </Reveal>

      <div className="mt-10 flex items-center gap-2">
        <Library className="h-5 w-5 text-neon-cyan" />
        <h2 className="font-display text-xl font-bold">Моя библиотека</h2>
      </div>

      {purchases.length === 0 ? (
        <div className="glass mt-6 p-10 text-center">
          <p className="text-white/50">Пока пусто — самое время выбрать что-нибудь 👇</p>
          <Link href="/catalog" className="btn-primary mt-5">
            В каталог
          </Link>
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {purchases.map((pur) => {
            const p = pur.product;
            const accent = ACCENT[p.category.accent] ?? ACCENT.violet;
            return (
              <Link key={pur.id} href={`/product/${p.slug}`} className="glass p-5 transition hover:-translate-y-1">
                <div className={`mb-3 grid h-11 w-11 place-items-center rounded-xl bg-white/5 ${accent.text}`}>
                  <CatIcon name={p.category.icon} className="h-5 w-5" />
                </div>
                <h3 className="font-display font-semibold">{p.title}</h3>
                <p className="mt-1 text-xs text-white/40">{p.category.title}</p>
                <span className="mt-3 inline-flex items-center gap-1 text-sm text-white/70">
                  {p.priceStars} <Star className="h-3.5 w-3.5 fill-neon-cyan text-neon-cyan" />
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
