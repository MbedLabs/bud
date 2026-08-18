/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar-background))",
          foreground: "hsl(var(--sidebar-foreground))",
          active: "hsl(var(--sidebar-active))",
          hover: "hsl(var(--sidebar-hover))",
          border: "hsl(var(--sidebar-border))",
        },
        bud: {
          leaf: "#22c55e",
          mint: "#dcfce7",
          forest: "#166534",
          deep: "#0f1a14",
          orange: "#f97316",
          gear: "#fb923c",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 5px rgba(34, 197, 94, 0.25)" },
          "50%": { boxShadow: "0 0 20px rgba(249, 115, 22, 0.35)" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-left": {
          from: { opacity: "0", transform: "translateX(-8px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "fade-in": "fade-in 0.3s ease-out",
        "slide-in-left": "slide-in-left 0.2s ease-out",
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
      backgroundImage: {
        "gradient-primary": "linear-gradient(135deg, #0f1a14, #22c55e, #f97316)",
        "gradient-hero": "linear-gradient(135deg, #166534, #4ade80, #fb923c)",
        "gradient-auth": "linear-gradient(to bottom right, #0f1a14, #2d8a45, #f97316)",
        "gradient-sidebar": "linear-gradient(180deg, #0f1a12 0%, #1a5c32 55%, #2a2418 100%)",
        "gradient-button": "linear-gradient(to right, hsl(var(--primary)), #f97316)",
        "gradient-card-hover": "linear-gradient(135deg, rgba(34,197,94,0.06), rgba(249,115,22,0.08))",
      },
      boxShadow: {
        elegant:
          "0 4px 6px -1px rgba(34, 197, 94, 0.12), 0 2px 4px -1px rgba(249, 115, 22, 0.1)",
        glow:
          "0 10px 25px -3px rgba(34, 197, 94, 0.28), 0 4px 6px -2px rgba(249, 115, 22, 0.15)",
        "inner-glow": "inset 0 1px 2px rgba(34, 197, 94, 0.12)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
