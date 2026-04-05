/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx}', './public/index.html'],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0a0f1e',
          800: '#0f172a',
          700: '#1e2a45',
          600: '#243356',
          500: '#2d4070',
        },
        scout: '#3b82f6',
        physio: '#ef4444',
        nutri: '#22c55e',
        accent: '#6366f1',
      },
    },
  },
  plugins: [],
};
