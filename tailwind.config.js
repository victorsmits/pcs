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
        // Fonds (surfaces) — pilotés par variables CSS pour le thème clair/sombre
        ink: {
          900: 'rgb(var(--ink-900) / <alpha-value>)',
          850: 'rgb(var(--ink-850) / <alpha-value>)',
          800: 'rgb(var(--ink-800) / <alpha-value>)',
          700: 'rgb(var(--ink-700) / <alpha-value>)',
          600: 'rgb(var(--ink-600) / <alpha-value>)',
          500: 'rgb(var(--ink-500) / <alpha-value>)',
        },
        // Nuances de texte — pilotées par variables (basculent en thème clair)
        slate: {
          200: 'rgb(var(--sl-200) / <alpha-value>)',
          300: 'rgb(var(--sl-300) / <alpha-value>)',
          400: 'rgb(var(--sl-400) / <alpha-value>)',
          500: 'rgb(var(--sl-500) / <alpha-value>)',
          600: 'rgb(var(--sl-600) / <alpha-value>)',
        },
        // Texte principal (remplace text-white sur surfaces)
        fg: 'rgb(var(--fg) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['"Fira Sans"', 'system-ui', 'sans-serif'],
        mono: ['"Fira Code"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
};
