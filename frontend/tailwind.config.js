/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['IBM Plex Sans', 'system-ui', 'sans-serif'],
      },
      colors: {
        graph: {
          bg: '#0a0e1a',
          surface: '#111827',
          border: '#1e293b',
          accent: '#6366f1',
          accent2: '#22d3ee',
          node: '#1a2235',
          llm: '#1a1a35',
        }
      }
    },
  },
  plugins: [],
}
