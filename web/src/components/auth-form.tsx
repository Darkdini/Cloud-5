"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Loader2, Mail, Lock, User } from "lucide-react";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const fd = new FormData(e.currentTarget);
    const payload = Object.fromEntries(fd.entries());
    const res = await fetch(`/api/auth/${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      router.refresh();
      router.push("/dashboard");
    } else {
      const d = await res.json().catch(() => ({}));
      setError(d.error ?? "Что-то пошло не так");
      setLoading(false);
    }
  }

  const isReg = mode === "register";

  return (
    <motion.div
      initial={{ opacity: 0, y: 24, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="glass w-full max-w-md p-8 shadow-glow"
    >
      <h1 className="font-display text-2xl font-bold">
        {isReg ? "Создать аккаунт" : "С возвращением"}
      </h1>
      <p className="mt-1 text-sm text-white/50">
        {isReg
          ? "Регистрируйся и получай доступ к покупкам"
          : "Войди, чтобы продолжить"}
      </p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        {isReg && (
          <label className="block">
            <span className="mb-1.5 flex items-center gap-2 text-xs text-white/60">
              <User className="h-3.5 w-3.5" /> Имя
            </span>
            <input name="name" required minLength={2} className="field" placeholder="Как тебя зовут" />
          </label>
        )}
        <label className="block">
          <span className="mb-1.5 flex items-center gap-2 text-xs text-white/60">
            <Mail className="h-3.5 w-3.5" /> Email
          </span>
          <input name="email" type="email" required className="field" placeholder="you@mail.com" />
        </label>
        <label className="block">
          <span className="mb-1.5 flex items-center gap-2 text-xs text-white/60">
            <Lock className="h-3.5 w-3.5" /> Пароль
          </span>
          <input
            name="password"
            type="password"
            required
            minLength={6}
            className="field"
            placeholder="••••••••"
          />
        </label>

        {error && <p className="text-sm text-neon-pink">{error}</p>}

        <button type="submit" disabled={loading} className="btn-primary w-full">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : isReg ? "Зарегистрироваться" : "Войти"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-white/50">
        {isReg ? "Уже есть аккаунт?" : "Нет аккаунта?"}{" "}
        <Link href={isReg ? "/login" : "/register"} className="text-gradient font-semibold">
          {isReg ? "Войти" : "Регистрация"}
        </Link>
      </p>
    </motion.div>
  );
}
