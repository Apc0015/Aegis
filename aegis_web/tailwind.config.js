/** @type {import('tailwindcss').Config} */
const withAlpha = (v) => `oklch(var(${v}) / <alpha-value>)`;

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: withAlpha("--bg"),
        surface: withAlpha("--surface"),
        card: withAlpha("--card"),
        elevated: withAlpha("--elevated"),
        border: withAlpha("--border"),
        "border-strong": withAlpha("--border-strong"),
        ink: {
          DEFAULT: withAlpha("--ink"),
          muted: withAlpha("--ink-muted"),
          faint: withAlpha("--ink-faint"),
        },
        accent: {
          DEFAULT: withAlpha("--accent"),
          strong: withAlpha("--accent-strong"),
          ink: withAlpha("--accent-ink"),
        },
        success: withAlpha("--success"),
        warning: withAlpha("--warning"),
        danger: withAlpha("--danger"),
        ring: withAlpha("--ring"),
      },
      fontFamily: {
        sans: ['"Inter Variable"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 3px)",
        sm: "calc(var(--radius) - 5px)",
        xl: "calc(var(--radius) + 4px)",
      },
      boxShadow: {
        // Reserved for true overlays only — cards use borders + surfaces.
        pop: "0 12px 32px -8px oklch(0 0 0 / 0.55), 0 4px 10px -4px oklch(0 0 0 / 0.4)",
        panel: "0 1px 2px oklch(0 0 0 / 0.3)",
        "accent-glow": "0 0 0 1px oklch(var(--accent) / 0.4), 0 8px 24px -8px oklch(var(--accent) / 0.35)",
      },
      transitionTimingFunction: {
        "out-quart": "cubic-bezier(0.25, 1, 0.5, 1)",
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.97)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.15" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 oklch(var(--success) / 0.5)" },
          "70%": { boxShadow: "0 0 0 5px oklch(var(--success) / 0)" },
          "100%": { boxShadow: "0 0 0 0 oklch(var(--success) / 0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.35s var(--ease-out-expo) both",
        "fade-in": "fade-in 0.25s ease-out both",
        "scale-in": "scale-in 0.16s var(--ease-out-quart) both",
        blink: "blink 1.1s step-end infinite",
        shimmer: "shimmer 1.6s infinite",
        "pulse-ring": "pulse-ring 2s ease-out infinite",
      },
    },
  },
  plugins: [],
};
