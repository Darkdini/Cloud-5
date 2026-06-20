"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Star } from "lucide-react";
import { CatIcon, ACCENT } from "./icon";

export type CardProduct = {
  slug: string;
  title: string;
  tagline: string;
  priceStars: number;
  badge: string;
  rating: number;
  sales: number;
  category: { title: string; icon: string; accent: string };
};

export function ProductCard({ p, index = 0 }: { p: CardProduct; index?: number }) {
  const accent = ACCENT[p.category.accent] ?? ACCENT.violet;
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5, delay: (index % 6) * 0.06 }}
      whileHover={{ y: -6 }}
    >
      <Link
        href={`/product/${p.slug}`}
        className={`glass group relative block overflow-hidden p-5 ring-1 ring-transparent transition hover:${accent.ring} hover:${accent.glow}`}
      >
        {/* световой блик */}
        <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-white/10 opacity-0 blur-2xl transition group-hover:opacity-100" />

        <div className="mb-4 flex items-start justify-between">
          <div
            className={`grid h-12 w-12 place-items-center rounded-xl bg-white/5 ${accent.text}`}
          >
            <CatIcon name={p.category.icon} className="h-6 w-6" />
          </div>
          {p.badge && (
            <span className="chip border-white/20 text-white/90">{p.badge}</span>
          )}
        </div>

        <p className="mb-1 text-xs text-white/40">{p.category.title}</p>
        <h3 className="font-display text-lg font-semibold leading-tight">{p.title}</h3>
        <p className="mt-1 line-clamp-2 text-sm text-white/55">{p.tagline}</p>

        <div className="mt-5 flex items-center justify-between">
          <span className="inline-flex items-center gap-1.5 text-sm font-semibold">
            {p.priceStars}
            <Star className="h-4 w-4 fill-neon-cyan text-neon-cyan" />
          </span>
          <span className="inline-flex items-center gap-3 text-xs text-white/40">
            <span className="inline-flex items-center gap-1">
              <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
              {p.rating}.0
            </span>
            <span>{p.sales} продаж</span>
          </span>
        </div>
      </Link>
    </motion.div>
  );
}
