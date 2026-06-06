import typography from '@tailwindcss/typography'

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'selector',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Helvetica', 'Arial', 'sans-serif'],
        display: ['Fraunces', 'ui-serif', 'Georgia', 'Cambria', 'Times New Roman', 'serif'],
      },
      colors: {
        // `primary` repointed from indigo to slate so any holdout class inherits
        // the new neutral palette. Use `text-indigo-700` / `dark:text-indigo-300`
        // directly when an accent is genuinely warranted (hover, active).
        primary: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },
      },
      backgroundImage: {
        'surface-light': 'linear-gradient(180deg, #ffffff 0%, #f3f5f2 100%)',
        'surface-dark': 'linear-gradient(180deg, rgba(31, 39, 54, 0.88) 0%, rgba(22, 28, 40, 0.88) 100%)',
      },
      boxShadow: {
        card: '0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px -12px rgba(15, 23, 42, 0.10)',
        'card-hover': '0 2px 4px rgba(15, 23, 42, 0.06), 0 16px 36px -14px rgba(15, 23, 42, 0.18)',
      },
      borderRadius: {
        card: '1.5rem',
      },
    },
  },
  plugins: [
    typography,
  ],
}
