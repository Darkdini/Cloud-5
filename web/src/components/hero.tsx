"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Zap } from "lucide-react";

export function Hero({ productCount }: { productCount: number }) {
  return (
    <section className="relative overflow-hidden pt-20 pb-16 sm:pt-28">
      <div className="container-x text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs text-white/70"
        >
          <Zap className="h-3.5 w-3.5 text-neon-cyan" />
          Маркетплейс цифровых товаров будущего
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 }}
          className="font-display text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl"
        >
          Покупай и продавай <br />
          <span className="text-gradient">боты, игры и код</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="mx-auto mt-5 max-w-xl text-base text-white/55 sm:text-lg"
        >
          Телеграм-боты, исходники игр, скрипты и ассеты в одном месте.
          Живой каталог, мгновенный доступ, оплата звёздами.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.3 }}
          className="mt-8 flex items-center justify-center gap-3"
        >
          <Link href="/catalog" className="btn-primary">
            Открыть каталог <ArrowRight className="h-4 w-4" />
          </Link>
          <Link href="/register" className="btn-ghost">
            Создать аккаунт
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 0.5 }}
          className="mt-10 flex items-center justify-center gap-8 text-sm text-white/40"
        >
          <Stat value={`${productCount}+`} label="товаров" />
          <span className="h-8 w-px bg-white/10" />
          <Stat value="4" label="раздела" />
          <span className="h-8 w-px bg-white/10" />
          <Stat value="24/7" label="доступ" />
        </motion.div>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <div className="font-display text-2xl font-bold text-white">{value}</div>
      <div className="text-xs">{label}</div>
    </div>
  );
}
