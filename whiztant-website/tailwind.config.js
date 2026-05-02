/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-dark': '#0a0a0a',
        'bg-card': '#111111',
        'bg-hover': '#1a1a1a',
        'text-primary': '#f5f5f5',
        'text-secondary': '#888888',
        'border-subtle': 'rgba(255,255,255,0.06)',
        'primary': '#e85d4a',
        'primary-light': '#ff8a65',
        'primary-dark': '#c94a3a',
        'warm': '#ffd54f',
        'success': '#4caf50',
        'warning': '#ffaa00',
        'error': '#ff4444',
      },
      fontFamily: {
        display: ['"Unbounded"', 'sans-serif'],
        body: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
