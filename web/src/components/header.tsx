"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Boxes, LogOut, LayoutDashboard } from "lucide-react";
import type { SessionUser } from "@/lib/auth";

export function Header({ user }: { user: SessionUser | null }) {
  const router = useRouter();

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.refresh();
    router.push("/");
  }

  return (
    <motion.header
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      className="sticky top-0 z-50 border-b border-white/10 bg-bg/60 backdrop-blur-xl"
    >
      <div className="container-x flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-neon-violet to-neon-cyan shadow-glow">
            <Boxes className="h-5 w-5 text-white" />
          </span>
          <span className="font-display text-lg font-bold tracking-tight">
            Cloud<span className="text-gradient">-5</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-6 text-sm text-white/70 md:flex">
          <Link href="/catalog" className="transition hover:text-white">
            Каталог
          </Link>
          <Link href="/#sections" className="transition hover:text-white">
            Разделы
          </Link>
          <Link href="/#how" className="transition hover:text-white">
            Как это работает
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          {user ? (
            <>
              <Link href="/dashboard" className="btn-ghost px-3 py-2">
                <LayoutDashboard className="h-4 w-4" />
                <span className="hidden sm:inline">{user.name}</span>
              </Link>
              <button onClick={logout} className="btn-ghost px-3 py-2" aria-label="Выйти">
                <LogOut className="h-4 w-4" />
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="btn-ghost px-4 py-2">
                Вход
              </Link>
              <Link href="/register" className="btn-primary px-4 py-2">
                Регистрация
              </Link>
            </>
          )}
        </div>
      </div>
    </motion.header>
  );
}
