import {
  Bot,
  Gamepad2,
  Code2,
  Palette,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

const MAP: Record<string, LucideIcon> = {
  bot: Bot,
  gamepad: Gamepad2,
  code: Code2,
  palette: Palette,
  sparkles: Sparkles,
};

export function CatIcon({
  name,
  className,
}: {
  name: string;
  className?: string;
}) {
  const Cmp = MAP[name] ?? Sparkles;
  return <Cmp className={className} />;
}

/** Tailwind-классы свечения по ключу акцента. */
export const ACCENT: Record<string, { text: string; ring: string; glow: string }> = {
  cyan: { text: "text-neon-cyan", ring: "ring-neon-cyan/40", glow: "shadow-glow-cyan" },
  violet: { text: "text-neon-violet", ring: "ring-neon-violet/40", glow: "shadow-glow" },
  pink: { text: "text-neon-pink", ring: "ring-neon-pink/40", glow: "shadow-glow" },
  lime: { text: "text-neon-lime", ring: "ring-neon-lime/40", glow: "shadow-glow" },
};
