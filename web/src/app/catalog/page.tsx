import Link from "next/link";
import { prisma } from "@/lib/db";
import { ProductCard } from "@/components/product-card";
import { Reveal } from "@/components/reveal";
import { CatIcon } from "@/components/icon";

export const dynamic = "force-dynamic";

export default async function CatalogPage({
  searchParams,
}: {
  searchParams: Promise<{ cat?: string }>;
}) {
  const { cat } = await searchParams;

  const [categories, products] = await Promise.all([
    prisma.category.findMany({ orderBy: { title: "asc" } }),
    prisma.product.findMany({
      where: cat ? { category: { slug: cat } } : undefined,
      include: { category: true },
      orderBy: { sales: "desc" },
    }),
  ]);

  const active = categories.find((c) => c.slug === cat);

  return (
    <div className="container-x py-12">
      <Reveal>
        <h1 className="font-display text-3xl font-bold sm:text-4xl">
          {active ? active.title : "Каталог"}
        </h1>
        <p className="mt-1 text-white/50">
          {products.length} товаров {active ? `в разделе «${active.title}»` : "на площадке"}
        </p>
      </Reveal>

      {/* Фильтр-пилюли */}
      <div className="mt-6 flex flex-wrap gap-2">
        <FilterPill href="/catalog" active={!cat} label="Все" icon="sparkles" />
        {categories.map((c) => (
          <FilterPill
            key={c.id}
            href={`/catalog?cat=${c.slug}`}
            active={cat === c.slug}
            label={c.title}
            icon={c.icon}
          />
        ))}
      </div>

      {products.length === 0 ? (
        <p className="mt-16 text-center text-white/40">В этом разделе пока пусто.</p>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((p, i) => (
            <ProductCard key={p.id} p={p} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}

function FilterPill({
  href,
  active,
  label,
  icon,
}: {
  href: string;
  active: boolean;
  label: string;
  icon: string;
}) {
  return (
    <Link
      href={href}
      className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition ${
        active
          ? "border-transparent bg-gradient-to-r from-neon-violet to-neon-pink text-white shadow-glow"
          : "border-white/10 bg-white/5 text-white/70 hover:border-white/25 hover:text-white"
      }`}
    >
      <CatIcon name={icon} className="h-4 w-4" />
      {label}
    </Link>
  );
}
