/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/renderer/**/*.{html,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Geist', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['Geist Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
