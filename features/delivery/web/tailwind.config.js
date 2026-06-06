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
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  darkMode: "class",
  plugins: [
    nextui({
      defaultTheme: "light",
      themes: {
        light: {
          colors: {
            background: "#f8fafc",
            foreground: "#0f172a",
            primary: { DEFAULT: "#0891b2", foreground: "#ffffff" },
            secondary: { DEFAULT: "#10b981", foreground: "#ffffff" },
            focus: "#3b82f6",
          },
        },
      },
    }),
  ],
};
