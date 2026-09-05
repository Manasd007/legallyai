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
        // "serif" is the heading utility (now Clash Display, a characterful
        // display grotesk — utility name kept so existing `font-serif` call
        // sites don't need to change).
        serif: ["var(--font-serif)", "system-ui", "sans-serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      // Brutalist: flatten the radius scale so every existing `rounded-*` call
      // site becomes crisp and boxy. `full` stays for pills, dots and avatars.
      borderRadius: {
        none: "0",
        sm: "0",
        DEFAULT: "2px",
        md: "2px",
        lg: "3px",
        xl: "4px",
        "2xl": "5px",
        "3xl": "6px",
        full: "9999px",
      },
      boxShadow: {
        // Hard offset shadows (no blur) — the brutalist signature. Cast in
        // `--c-ink` so they invert with the theme (near-black in light, a
        // crisp white ledge in dark). `card`/`lift` keep their names so every
        // existing call site flips automatically.
        card: "3px 3px 0 0 rgb(var(--c-ink) / 0.9)",
        lift: "6px 6px 0 0 rgb(var(--c-ink))",
        brutal: "4px 4px 0 0 rgb(var(--c-ink))",
        "brutal-sm": "2px 2px 0 0 rgb(var(--c-ink))",
        "brutal-lg": "8px 8px 0 0 rgb(var(--c-ink))",
        "brutal-gold": "4px 4px 0 0 rgb(var(--c-gold-500))",
      },
      maxWidth: { content: "72rem" },
    },
  },
  plugins: [],
};
