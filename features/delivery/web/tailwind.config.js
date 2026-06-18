import { nextui } from "@nextui-org/react";

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "./node_modules/@nextui-org/theme/dist/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        heading: ["Space Grotesk", "sans-serif"],
        sans: ["Outfit", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        canvas: "#0a0e1a",
        surface: "#0f1525",
        nvidia: "#76b900",
        "electric-cyan": "#00d4ff",
        "neon-green": "#00ff88",
        "warm-amber": "#f97316",
        "soft-purple": "#a855f7",
        "text-primary": "#e8edf5",
        "text-secondary": "#8b95a8",
        cyan: {
          neon: "#66FCF1",
        },
        obsidian: {
          DEFAULT: "#08090C",
        },
        matrix: {
          DEFAULT: "rgba(18, 22, 29, 0.40)",
        },
        crimson: {
          DEFAULT: "#FF3366",
        },
        amber: {
          DEFAULT: "#FFB347",
        },
        emerald: {
          DEFAULT: "#00FA9A",
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
      },
      keyframes: {
        "gradient-drift": {
          "0%, 100%": { transform: "translate(0%, 0%)" },
          "50%": { transform: "translate(3%, -3%)" },
        },
      },
      animation: {
        "gradient-drift": "gradient-drift 20s ease-in-out infinite",
      },
    },
  },
  darkMode: "class",
  plugins: [
    nextui({
      defaultTheme: "dark",
      themes: {
        dark: {
          colors: {
            background: "#08090C",
            foreground: "#E0E6ED",
            primary: { DEFAULT: "#66FCF1", foreground: "#08090C" },
            secondary: { DEFAULT: "#00FA9A", foreground: "#08090C" },
            danger: { DEFAULT: "#FF3366", foreground: "#ffffff" },
            warning: { DEFAULT: "#FFB347", foreground: "#08090C" },
            focus: "#66FCF1",
          },
        },
      },
    }),
  ],
};
