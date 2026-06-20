import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { getSessionUser } from "@/lib/auth";
import { BuyButton } from "@/components/buy-button";
import { CatIcon, ACCENT } from "@/components/icon";
import { Star, ArrowLeft, Check } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function ProductPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const product = await prisma.product.findUnique({
    where: { slug },
    include: { category: true },
  });
  if (!product) notFound();

  const user = await getSessionUser();
  let owned = false;
  if (user) {
    owned = !!(await prisma.purchase.findUnique({
      where: { userId_productId: { userId: user.id, productId: product.id } },
    }));
  }

  const accent = ACCENT[product.category.accent] ?? ACCENT.violet;
  const features = product.description.split("\n").filter(Boolean);

  return (
    <div className="container-x py-10">
      <Link href="/catalog" className="mb-6 inline-flex items-center gap-2 text-sm text-white/50 hover:text-white">
        <ArrowLeft className="h-4 w-4" /> Назад в каталог
      </Link>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1.4fr_1fr]">
        {/* Левая часть */}
        <div>
          <div
            className={`glass relative flex h-56 items-center justify-center overflow-hidden ${accent.glow}`}
          >
            <div className={`${accent.text}`}>
              <CatIcon name={product.category.icon} className="h-24 w-24 opacity-80" />
            </div>
            {product.badge && (
              <span className="chip absolute left-4 top-4 border-white/20 text-white">
                {product.badge}
              </span>
            )}
          </div>

          <Link
            href={`/catalog?cat=${product.category.slug}`}
            className={`mt-6 inline-flex items-center gap-2 text-sm ${accent.text}`}
          >
            <CatIcon name={product.category.icon} className="h-4 w-4" />
            {product.category.title}
          </Link>

          <h1 className="mt-2 font-display text-3xl font-bold sm:text-4xl">
            {product.title}
          </h1>
          <p className="mt-2 text-white/55">{product.tagline}</p>

          {features.length > 0 && (
            <div className="mt-8">
              <h2 className="font-display text-lg font-semibold">Что входит</h2>
              <ul className="mt-3 space-y-2">
                {features.map((f, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm text-white/70">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-neon-lime" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Правая часть — покупка */}
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <div className="glass p-6 shadow-glow">
            <div className="flex items-baseline gap-2">
              <span className="font-display text-4xl font-bold">{product.priceStars}</span>
              <Star className="h-6 w-6 fill-neon-cyan text-neon-cyan" />
            </div>
            <p className="mt-1 text-xs text-white/40">оплата звёздами Telegram</p>

            <div className="my-5 flex items-center justify-between text-sm text-white/60">
              <span className="inline-flex items-center gap-1">
                <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                {product.rating}.0
              </span>
              <span>{product.sales} продаж</span>
            </div>

            <BuyButton
              productId={product.id}
              priceStars={product.priceStars}
              authed={!!user}
              owned={owned}
            />

            {!user && (
              <p className="mt-3 text-center text-xs text-white/40">
                <Link href="/login" className="text-gradient">Войди</Link>, чтобы купить
              </p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
