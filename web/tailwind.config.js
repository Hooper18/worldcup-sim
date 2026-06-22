/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // 色值来自 index.css 的 CSS 变量（亮/暗双主题），rgb(var / <alpha-value>) 支持 /透明度
        paper: 'rgb(var(--c-paper) / <alpha-value>)',
        surface: 'rgb(var(--c-surface) / <alpha-value>)',
        card: 'rgb(var(--c-card) / <alpha-value>)',
        ink: {
          DEFAULT: 'rgb(var(--c-ink) / <alpha-value>)',
          secondary: 'rgb(var(--c-ink-secondary) / <alpha-value>)',
          faint: 'rgb(var(--c-ink-faint) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'rgb(var(--c-accent) / <alpha-value>)',
          soft: 'rgb(var(--c-accent-soft) / <alpha-value>)',
        },
        line: 'rgb(var(--c-line) / <alpha-value>)',
      },
      fontSize: {
        // 界面文字 13-15px 为主（Apple HIG 节奏）
        xs: ['12px', '1.6'],
        sm: ['13px', '1.7'],
        base: ['14px', '1.7'],
        md: ['15px', '1.7'],
        lg: ['18px', '1.6'],
        xl: ['20px', '1.5'],
      },
    },
  },
  plugins: [],
}
