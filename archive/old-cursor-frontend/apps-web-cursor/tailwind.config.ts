import type { Config } from "tailwindcss";

/**
 * FE-00: Brand Spec §3.3 — semantic Tailwind mapping.
 * All colors from CSS variables; no hardcoded hex.
 */
const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        background: "hsl(var(--bg))",
        foreground: "hsl(var(--text))",
        primary: {
          DEFAULT: "hsl(var(--action))",
          foreground: "hsl(var(--action-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--surface-2))",
          foreground: "hsl(var(--text-muted))",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--border))",
        ring: "hsl(var(--focus))",
        destructive: "hsl(var(--danger))",
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        highlight: "hsl(var(--highlight))",
      },
      borderRadius: {
        sm: "10px",
        md: "12px",
        lg: "16px",
        xl: "20px",
      },
      boxShadow: {
        sm: "0 1px 2px hsl(var(--border) / 0.1)",
        md: "0 4px 8px hsl(var(--border) / 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
