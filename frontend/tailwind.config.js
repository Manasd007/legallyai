// Globs are resolved relative to process.cwd() (the repo root, since the dev
// server runs from there), so anchor them to this config's own directory.
const dir = __dirname.replace(/\\/g, "/");

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [`${dir}/app/**/*.{ts,tsx}`, `${dir}/components/**/*.{ts,tsx}`],
  theme: {
    extend: {
      colors: {
        // Theme-aware surfaces/text (flip between light/dark via CSS vars).
        parchment: "rgb(var(--c-parchment) / <alpha-value>)", // page background
        ink: "rgb(var(--c-ink) / <alpha-value>)", // primary text + hairlines
        surface: "rgb(var(--c-surface) / <alpha-value>)", // cards, inputs

        // Theme-aware primary button (dark-on-cream → near-white-on-black).
        brand: "rgb(var(--c-brand) / <alpha-value>)",
        onbrand: "rgb(var(--c-on-brand) / <alpha-value>)",

        // Fixed tokens (same in both themes).
        cream: "#f4f1ea", // light text used on dark editorial surfaces
        // Neutral charcoal scale (replaces the old cold navy); used for dark
        // panels, icon chips and editorial bands in both themes. Kept neutral
        // so dark mode reads black/white rather than warm.
        navy: {
          700: "#2a2a2d",
          800: "#1e1e21",
          900: "#161618",
          950: "#0d0d0e",
        },
        // Theme-aware accent: warm gold in light, cool sage/jade in dark.
        // (Luminance inverts per theme so text steps stay readable on each bg.)
        gold: {
          300: "rgb(var(--c-gold-300) / <alpha-value>)",
          400: "rgb(var(--c-gold-400) / <alpha-value>)",
          500: "rgb(var(--c-gold-500) / <alpha-value>)",
          600: "rgb(var(--c-gold-600) / <alpha-value>)",
          700: "rgb(var(--c-gold-700) / <alpha-value>)",
        },
      },
      fontFamily: {
        // "serif" is the heading utility (now Satoshi, a sans — utility name
        // kept so existing `font-serif` call sites don't need to change).
        serif: ["var(--font-serif)", "system-ui", "sans-serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(11,22,38,0.04), 0 8px 24px -12px rgba(11,22,38,0.18)",
        lift: "0 2px 4px rgba(11,22,38,0.05), 0 18px 40px -18px rgba(11,22,38,0.28)",
      },
      maxWidth: { content: "72rem" },
    },
  },
  plugins: [],
};
