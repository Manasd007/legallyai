const path = require("path");

// The dev server runs from the repo root, so Tailwind's default config
// auto-discovery (which uses process.cwd()) misses frontend/tailwind.config.js.
// Point it at the config explicitly so our custom theme always loads.
module.exports = {
  plugins: {
    tailwindcss: { config: path.join(__dirname, "tailwind.config.js") },
    autoprefixer: {},
  },
};
