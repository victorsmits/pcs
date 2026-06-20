/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './**/templates/**/*.html',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Bleu data (primaire)
        brand: {
          50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd',
          400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8',
          800: '#1e40af', 900: '#1e3a8a', 950: '#172554',
        },
        // Accent amber (highlights)
        accent: {
          400: '#fbbf24', 500: '#f59e0b', 600: '#d97706',
        },
        // Rouge live
        live: {
          500: '#ef4444', 600: '#dc2626',
        },
        // Fonds slate (dark OLED)
        ink: {
          900: '#0b0f17', 850: '#0f1422', 800: '#131a2a', 700: '#1c2438',
          600: '#28324a', 500: '#3a4661',
        },
      },
      fontFamily: {
        sans: ['"Fira Sans"', 'system-ui', 'sans-serif'],
        mono: ['"Fira Code"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
};
