import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  "#f0f4ff",
          100: "#e0eaff",
          500: "#4264d4",
          600: "#3451b8",
          700: "#27409e",
          800: "#1c2f82",
          900: "#131f62",
        },
        legal: {
          gold:   "#c8a93c",
          dark:   "#1a1a2e",
          gray:   "#6b7280",
        },
      },
      fontFamily: {
        serif: ["Georgia", "Times New Roman", "serif"],
        sans:  ["var(--font-sans)", "system-ui", "sans-serif"],
        mono:  ["var(--font-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
