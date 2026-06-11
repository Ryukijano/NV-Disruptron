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
