"use client";

import { motion } from "framer-motion";

/** Живой неоновый фон: плавающие световые сферы + анимированная сетка. */
export function AnimatedBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <div className="grid-bg absolute inset-0 animate-grid-pan" />

      <motion.div
        className="absolute -left-32 top-10 h-96 w-96 rounded-full bg-neon-violet/30 blur-3xl"
        animate={{ y: [0, 40, 0], x: [0, 20, 0] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute -right-24 top-40 h-80 w-80 rounded-full bg-neon-cyan/25 blur-3xl"
        animate={{ y: [0, -50, 0], x: [0, -20, 0] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-neon-pink/20 blur-3xl"
        animate={{ y: [0, -30, 0] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}
