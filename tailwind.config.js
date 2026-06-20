/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          light: "#f7f5f0",
          DEFAULT: "#8c6239", // Warm wood brown
          dark: "#5c3d21",
        },
        primary: {
          light: "#f0f4f8",
          DEFAULT: "#1e3a8a", // Professional navy
          dark: "#1e293b",
        }
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      }
    },
  },
  plugins: [],
}
