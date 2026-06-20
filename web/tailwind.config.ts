import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
  ],
  safelist: [
    "text-neon-cyan", "text-neon-violet", "text-neon-pink", "text-neon-lime",
    "ring-neon-cyan/40", "ring-neon-violet/40", "ring-neon-pink/40", "ring-neon-lime/40",
    "hover:ring-neon-cyan/40", "hover:ring-neon-violet/40",
    "hover:ring-neon-pink/40", "hover:ring-neon-lime/40",
    "shadow-glow", "shadow-glow-cyan", "hover:shadow-glow", "hover:shadow-glow-cyan",
    "fill-neon-cyan", "text-neon-cyan",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#05060f",
        surface: "#0b0e1f",
        neon: {
          cyan: "#22d3ee",
          violet: "#a855f7",
          pink: "#ec4899",
          lime: "#a3e635",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 40px -10px rgba(168,85,247,0.5)",
        "glow-cyan": "0 0 40px -10px rgba(34,211,238,0.55)",
      },
      keyframes: {
        float: {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-12px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "grid-pan": {
          "0%": { backgroundPosition: "0 0" },
          "100%": { backgroundPosition: "40px 40px" },
        },
        "pulse-glow": {
          "0%,100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        float: "float 6s ease-in-out infinite",
        shimmer: "shimmer 3s linear infinite",
        "grid-pan": "grid-pan 8s linear infinite",
        "pulse-glow": "pulse-glow 4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
