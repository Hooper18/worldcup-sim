/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // 暖白底 + 极淡层级差（参照 Claude.ai 的暖白系）
        paper: '#FAF9F6',
        surface: '#F4F2EE',
        ink: {
          DEFAULT: '#1F1F1F',
          secondary: '#6B6B6B',
          faint: '#9C9A96',
        },
        // 单一低调强调色：深绿（草皮色系，克制不抢眼）
        accent: {
          DEFAULT: '#2F6B4F',
          soft: '#E8F0EB',
        },
        line: '#E7E4DE',
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
