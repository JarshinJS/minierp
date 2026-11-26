/** @type {import('tailwindcss').Config} */
const colors = require("tailwindcss/colors");

module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./apps/**/*.py",
    "./static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // Primary interactive colour (indigo). `light`/`dark` aliases are kept
        // because existing templates reference bg-brand-light / bg-brand-dark.
        brand: {
          ...colors.indigo,
          light: colors.indigo[50],
          DEFAULT: colors.indigo[600],
          dark: colors.indigo[700],
        },
        // Deep navy used by the application sidebar.
        navy: {
          700: "#243352",
          800: "#18233b",
          850: "#131c31",
          900: "#0e1627",
          950: "#090f1c",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        outfit: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.04)",
        pop: "0 10px 30px -10px rgb(15 23 42 / 0.25), 0 4px 8px -4px rgb(15 23 42 / 0.08)",
      },
    },
  },
  plugins: [],
};
